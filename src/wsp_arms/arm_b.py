"""Arm B: fine-tuning (B-full, B-lora) per spec section 5, plus a reusable trainer (also used by H and D-ft).

Recipe: fresh 2-logit linear head on the pooled feature (lr 1e-3); AdamW wd 0.05; cosine schedule with 5% warmup;
batch 16 (optional micro-batching with gradient accumulation); bf16 autocast over fp32 master weights; gradient
checkpointing; steps = max(200, ceil(4 epochs / batch 16)); class-balanced CE weights; final-step model (no early
stopping); seed = 1000*r + k (k=all -> 993, the number of pool patients). B-full: lr 1e-5 with layer-wise decay 0.75.
B-lora: LoRA r=16 alpha=32 dropout 0.1 on attention q,k,v,o + MLP, lr 2e-4. Threshold fixed at 0.5.
Augmentation: RandomResizedCrop(scale .7-1, ratio .8-1.25), h-flip, rotation +-10 deg, brightness/contrast +-0.1.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np

from . import core

VARIANTS = ('full', 'lora')
RECIPE = dict(
    head_lr=1e-3, weight_decay=0.05, warmup=0.05, batch=16, min_steps=200, epochs=4, bf16=True, gradient_checkpointing=True,
    full=dict(lr=1e-5, layer_decay=0.75),
    lora=dict(lr=2e-4, rank=16, alpha=32, dropout=0.1),
    aug=dict(scale=(0.7, 1.0), ratio=(0.8, 1.25), hflip=0.5, rotate_deg=10.0, brightness=0.1, contrast=0.1),
    threshold=0.5, vram_cap_gb=7.5, test_batch=4)
ALL_SEED_K = 993  # training seed for k='all' (= number of pool patients)


def _toolkit():
    try:
        import wsp_toolkit  # noqa: F401
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'toolkit'))
    from wsp_toolkit import training
    return training


def arm_name(variant):
    return f'B-{variant}'


def train_seed(k, r):
    return 1000 * int(r) + (ALL_SEED_K if k == 'all' else int(k))


def n_steps(n_images, batch=16):
    return max(RECIPE['min_steps'], math.ceil(RECIPE['epochs'] * n_images / batch))


# ------------------------------------------------------------------ data
def augment(im, rng, enc_name, aug=None):
    """Deterministic (given rng) augmentation of a PIL image; returns an RGB PIL image of the original size class."""
    from PIL import Image, ImageEnhance
    a = aug or RECIPE['aug']
    method = Image.Resampling.BILINEAR if enc_name == 'dinov3' else Image.Resampling.BICUBIC
    im = im.convert('RGB')
    W, H = im.size
    area = W * H
    box = None
    for _ in range(10):
        s = rng.uniform(*a['scale']) * area
        ar = math.exp(rng.uniform(math.log(a['ratio'][0]), math.log(a['ratio'][1])))
        w, h = int(round(math.sqrt(s * ar))), int(round(math.sqrt(s / ar)))
        if 0 < w <= W and 0 < h <= H:
            x0, y0 = int(rng.integers(0, W - w + 1)), int(rng.integers(0, H - h + 1))
            box = (x0, y0, x0 + w, y0 + h)
            break
    if box is None:
        box = (0, 0, W, H)
    im = im.crop(box)
    if rng.random() < a['hflip']:
        im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    im = im.rotate(float(rng.uniform(-a['rotate_deg'], a['rotate_deg'])), resample=Image.Resampling.BICUBIC)
    im = ImageEnhance.Brightness(im).enhance(float(rng.uniform(1 - a['brightness'], 1 + a['brightness'])))
    im = ImageEnhance.Contrast(im).enhance(float(rng.uniform(1 - a['contrast'], 1 + a['contrast'])))
    return im


class TrainSet:
    """steps*batch (image, label) draws: seeded epoch-wise permutations, per-draw seeded augmentation."""

    def __init__(self, enc, files, labels, seed, n_draws, aug=True):
        self.enc, self.files, self.labels, self.seed, self.aug = enc, list(files), np.asarray(labels), seed, aug
        rng = np.random.default_rng(seed)
        n = len(self.files)
        order = []
        while len(order) < n_draws:
            order.extend(rng.permutation(n).tolist())
        self.order = order[:n_draws]

    def __len__(self):
        return len(self.order)

    def __getitem__(self, i):
        from PIL import Image
        from wsp_ml.encoders import preprocess
        j = self.order[i]
        with Image.open(self.files[j]) as im:
            im.load()
        if self.aug:
            im = augment(im, np.random.default_rng((self.seed, i)), self.enc)
        import torch
        return preprocess(im, self.enc), torch.tensor(int(self.labels[j]))


class ImageSet:
    def __init__(self, enc, files):
        self.enc, self.files = enc, list(files)

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        from PIL import Image
        from wsp_ml.encoders import preprocess
        with Image.open(self.files[i]) as im:
            return preprocess(im, self.enc)


# ------------------------------------------------------------------ model
def layer_id(name, num_layers):
    """0 = embeddings, 1..L = transformer blocks, L+1 = everything after (final norm, pooler/MAP head)."""
    m = re.search(r'(?:^|\.)layers?\.(\d+)\.', name)
    if m:
        return int(m.group(1)) + 1
    if 'embeddings' in name or 'embed' in name.split('.')[0]:
        return 0
    return num_layers + 1


def build_model(enc, variant, device='cuda', head_state=None, seed=0):
    """Encoder in fp32 (master weights) + fresh 2-logit head; returns (Classifier, param_groups, adapter)."""
    import torch
    from wsp_ml.encoders import load_encoder
    tr = _toolkit()
    torch.manual_seed(seed)
    adapter = load_encoder(enc, device, torch.float32)
    tr.finetune_adapter(adapter, mode=variant, rank=RECIPE['lora']['rank'], alpha=RECIPE['lora']['alpha'],
                        dropout=RECIPE['lora']['dropout'], gradient_checkpointing=RECIPE['gradient_checkpointing'])
    head = torch.nn.Linear(adapter.hidden_size, 2)
    if head_state is not None:
        head.load_state_dict(head_state)
    model = tr.Classifier(adapter, head).to(device)
    L = adapter.num_layers
    groups = [{'params': list(head.parameters()), 'lr': RECIPE['head_lr'], 'name': 'head'}]
    if variant == 'lora':
        ps = [p for n, p in model.backbone.named_parameters() if p.requires_grad]
        groups.append({'params': ps, 'lr': RECIPE['lora']['lr'], 'name': 'lora'})
    else:
        by = {}
        for n, p in model.backbone.named_parameters():
            if p.requires_grad:
                by.setdefault(layer_id(n, L), []).append(p)
        for lid, ps in sorted(by.items()):
            groups.append({'params': ps, 'lr': RECIPE['full']['lr'] * RECIPE['full']['layer_decay'] ** (L + 1 - lid), 'name': f'layer{lid}'})
    return model, groups, adapter


def class_weights(labels):
    labels = np.asarray(labels)
    n = len(labels)
    return [n / (2 * max(1, int((labels == c).sum()))) for c in (0, 1)]


def train_model(model, groups, enc, files, labels, seed, *, steps=None, micro_batch=None, num_workers=4, device='cuda', log=None):
    """Train for `steps` (default per recipe). Returns dict with losses and timing."""
    import torch
    tr = _toolkit()
    batch = RECIPE['batch']
    steps = n_steps(len(files), batch) if steps is None else steps
    mb = micro_batch or (1 if enc == 'medsiglip' else 2)
    if mb < 1 or batch % mb:
        raise ValueError('micro_batch must be a positive divisor of 16')
    if steps < 1:
        raise ValueError('steps must be positive')
    acc = batch // mb
    ds = TrainSet(enc, files, labels, seed, steps * batch)
    g = torch.Generator().manual_seed(seed)
    loader = torch.utils.data.DataLoader(ds, batch_size=mb, shuffle=False, num_workers=num_workers, drop_last=True,
                                         persistent_workers=False, generator=g)
    t0 = time.monotonic()
    losses = tr.fit(model, loader, steps=steps, weight_decay=RECIPE['weight_decay'], warmup=RECIPE['warmup'], param_groups=groups,
                    accumulate=acc, class_weights=class_weights(labels), autocast=torch.bfloat16 if RECIPE['bf16'] else None, device=device)
    torch.cuda.synchronize()
    return {'steps': steps, 'losses': losses, 'seconds': time.monotonic() - t0}


def predict_files(model, enc, files, device='cuda', num_workers=4):
    import torch
    tr = _toolkit()
    loader = torch.utils.data.DataLoader(ImageSet(enc, files), batch_size=RECIPE['test_batch'], shuffle=False, num_workers=num_workers)
    p = tr.predict(model, loader, device=device, autocast=torch.bfloat16 if RECIPE['bf16'] else None)
    return p[:, 1].numpy().astype(np.float64)


def cap_vram():
    import torch
    total = torch.cuda.get_device_properties(0).total_memory / 2**30
    torch.cuda.set_per_process_memory_fraction(min(1.0, RECIPE['vram_cap_gb'] / total))
    torch.cuda.reset_peak_memory_stats()


# ------------------------------------------------------------------ run
def pool_files(paths, names):
    return [paths.root / 'data/pool' / n for n in names]


def run(arm, enc, k, r, paths=None, force=False, steps=None, micro_batch=None, run_dir=None):
    """Run B-full / B-lora for one (enc, k, r). `arm` is 'B-full' or 'B-lora'."""
    import torch
    paths = paths or core.Paths.default()
    variant = arm.split('-', 1)[1]
    if variant not in VARIANTS:
        raise ValueError(arm)
    k = core.parse_k(k)
    run_dir = Path(run_dir) if run_dir else paths.run_dir(arm, enc, k, r)
    if not force and core.is_complete(run_dir):
        return json.loads((run_dir / 'run.json').read_text())
    # A failed forced rerun must not leave a stale completion marker.
    (run_dir / 'run.json').unlink(missing_ok=True)
    t0 = time.monotonic()
    alloc = core.load_allocation(paths, k, r)
    test_names = sorted(p.name for p in paths.test_png_dir().glob('*.png'))
    if len(test_names) != core.N_TEST:
        raise ValueError('unexpected number of test PNGs')
    seed = train_seed(k, r)
    rec = {
        'arm': arm, 'encoder': enc, 'k': alloc.k, 'r': alloc.r, 'allocation_seed': alloc.seed, 'allocation_sha256': alloc.sha256,
        'n_train_patients': len(alloc.patient_ids), 'n_train_images': len(alloc.images), 'n_train_pos_images': int(alloc.labels.sum()),
        'train_image_list_sha256': core.sha256_text(alloc.images), 'training_seed': seed, 'recipe': RECIPE,
        'oof_metrics': None, 'threshold': RECIPE['threshold'], 'threshold_method': 'fixed_0.5_class_balanced_finetuned',
    }
    single = len(set(alloc.labels.tolist())) < 2
    if single:
        prior = float(alloc.labels.mean())
        probs = np.full(len(test_names), prior)
        rec.update(single_class=True, constant_prior=prior, threshold=0.5, threshold_method='fixed_0.5_single_class',
                   note='single-class allocation: constant training class prior (AUROC 0.5 by construction); no training')
        rec['timings_sec'] = {'total': time.monotonic() - t0}
        return core.write_run(paths, run_dir, rec, test_names, probs)
    cap_vram()
    files = pool_files(paths, alloc.images)
    t1 = time.monotonic()
    model, groups, adapter = build_model(enc, variant, seed=seed)
    t_load = time.monotonic() - t1
    info = train_model(model, groups, enc, files, alloc.labels, seed, steps=steps, micro_batch=micro_batch)
    t2 = time.monotonic()
    probs = predict_files(model, enc, [paths.test_png_dir() / n for n in test_names])
    t_pred = time.monotonic() - t2
    peak = torch.cuda.max_memory_allocated() / 2**30
    losses = info['losses']
    n_train = sum(p.numel() for g in groups for p in g['params'])
    rec.update(single_class=False, steps=info['steps'], micro_batch=micro_batch or (1 if enc == 'medsiglip' else 2), class_weights=class_weights(alloc.labels),
               n_trainable_params=int(n_train), param_groups=[{'name': g['name'], 'lr': g.get('base_lr', g['lr']), 'n': len(g['params'])} for g in groups],
               train_loss={'first10_mean': float(np.mean(losses[:10])), 'last10_mean': float(np.mean(losses[-10:])), 'min': float(np.min(losses)),
                           'all_finite': bool(np.all(np.isfinite(losses)))},
               peak_vram_gb=peak,
               timings_sec={'load_model': t_load, 'train': info['seconds'], 'predict_test': t_pred, 'total': time.monotonic() - t0})
    del model, adapter
    torch.cuda.empty_cache()
    return core.write_run(paths, run_dir, rec, test_names, probs)


# ------------------------------------------------------------------ timing / grid estimate
def time_one(enc, variant, paths=None, steps=50, micro_batch=None, n_pred=128):
    """50-step timing run on k=all/r=1 images (real data loading), + test-inference throughput on n_pred test images."""
    import torch
    paths = paths or core.Paths.default()
    alloc = core.load_allocation(paths, 'all', 1)
    cap_vram()
    t0 = time.monotonic()
    model, groups, adapter = build_model(enc, variant, seed=0)
    t_load = time.monotonic() - t0
    info = train_model(model, groups, enc, pool_files(paths, alloc.images), alloc.labels, 0, steps=steps, micro_batch=micro_batch)
    peak_train = torch.cuda.max_memory_allocated() / 2**30
    test = sorted(p.name for p in paths.test_png_dir().glob('*.png'))[:n_pred]
    t1 = time.monotonic()
    predict_files(model, enc, [paths.test_png_dir() / n for n in test])
    t_pred = time.monotonic() - t1
    peak = torch.cuda.max_memory_allocated() / 2**30
    out = {'encoder': enc, 'variant': variant, 'steps': steps, 'micro_batch': micro_batch or (1 if enc == 'medsiglip' else 2), 'load_sec': t_load,
           'train_sec': info['seconds'], 'sec_per_step': info['seconds'] / steps,
           'loss_first5': float(np.mean(info['losses'][:5])), 'loss_last5': float(np.mean(info['losses'][-5:])),
           'pred_images': len(test), 'pred_sec': t_pred, 'pred_img_per_sec': len(test) / t_pred,
           'peak_vram_train_gb': peak_train, 'peak_vram_gb': peak}
    del model, adapter
    torch.cuda.empty_cache()
    return out


def estimate_grid(timings, ks=core.KS, rs=core.RS, paths=None):
    """Estimated GPU hours for the full B grid from measured timings (list of time_one dicts)."""
    paths = paths or core.Paths.default()
    n_img = {k: len(core.load_allocation(paths, k, 1).images) for k in ks}
    est = {}
    total = 0.0
    for t in timings:
        per_run = []
        for k in ks:
            s = n_steps(n_img[k])
            # test inference measured on a subset; the 1,593-image pass is scaled; loading time added per run
            per_run.append(t['load_sec'] + s * t['sec_per_step'] + core.N_TEST / t['pred_img_per_sec'])
        hours = sum(per_run) * len(rs) / 3600
        est[f"{t['encoder']}/B-{t['variant']}"] = {'hours': hours, 'per_k_seconds': dict(zip(ks, per_run))}
        total += hours
    return {'by_arm': est, 'total_gpu_hours': total, 'n_runs': len(timings) * len(ks) * len(rs),
            'n_images_by_k': n_img, 'steps_by_k': {k: n_steps(n) for k, n in n_img.items()},
            'note': 'estimate = sum over k,r of (model load + steps*sec/step + 1593/pred_rate); 50-step timing includes dataloader warmup, so it is slightly pessimistic'}
