"""Arm H: external transfer pretraining and target continuation."""
from __future__ import annotations

import csv
import json
import math
import time
from pathlib import Path

import numpy as np

from . import arm_b, core

DATASETS = ('GRAZPEDWRI-DX', 'FracAtlas', 'MURA')
SAMPLE_SEED = 7


def external_sample(paths, n=40000):
    base = paths.root / 'data/external/extracted'
    manifests = paths.root / 'features/external-manifests'
    rows, counts, hashes = [], {}, {}
    for name in DATASETS:
        manifest = manifests / f'{name}.csv'
        hashes[name] = core.sha256_file(manifest)
        labels = []
        with manifest.open(newline='') as f:
            for row in csv.DictReader(f):
                label = int(row['label'])
                rel = Path(row['file'])
                if label not in (0, 1) or rel.is_absolute() or '..' in rel.parts:
                    raise ValueError(f'invalid manifest row in {name}')
                rows.append((base / rel, label))
                labels.append(label)
        counts[name] = {'images': len(labels), 'negative': labels.count(0), 'positive': labels.count(1)}
    if n < 1 or n > len(rows):
        raise ValueError('sample size outside manifest population')
    rng = np.random.default_rng(SAMPLE_SEED)
    chosen = [rows[i] for i in rng.choice(len(rows), size=n, replace=False)]
    if len({str(p) for p, _ in rows}) != len(rows):
        raise ValueError('duplicate external image paths')
    return chosen, counts, hashes


def pretrain_dir(paths, enc, sample_size):
    # Validation artifacts can never masquerade as the full transfer checkpoint.
    suffix = 'pretrain' if sample_size == 40000 else f'pretrain-validation-{sample_size}'
    return paths.private / 'runs/baselines/H' / enc / suffix


class ExternalTrainSet(arm_b.TrainSet):
    def __getitem__(self, i):
        # Some public source JPEGs are truncated; match Pillow's permissive decoding.
        from PIL import ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        return super().__getitem__(i)


def pretrain(enc, paths=None, sample_size=40000, force=False, micro_batch=None):
    import torch
    from safetensors.torch import save_file
    paths = paths or core.Paths.default()
    out = pretrain_dir(paths, enc, sample_size)
    marker, checkpoint = out / 'pretrain.json', out / 'transfer.safetensors'
    if not force and marker.exists() and checkpoint.exists():
        rec = json.loads(marker.read_text())
        if rec.get('status') == 'complete' and core.sha256_file(checkpoint) == rec['checkpoint_sha256']:
            return rec
    marker.unlink(missing_ok=True)
    started = time.monotonic()
    rows, counts, hashes = external_sample(paths, sample_size)
    files, labels = zip(*rows)
    arm_b.cap_vram()
    model, groups, adapter = arm_b.build_model(enc, 'lora', seed=SAMPLE_SEED)
    mb = micro_batch or (1 if enc == 'medsiglip' else 2)
    if mb < 1 or 16 % mb:
        raise ValueError('micro batch must divide 16')
    # TrainSet makes an independent seeded permutation: each sampled image appears exactly once.
    ds = ExternalTrainSet(enc, files, labels, SAMPLE_SEED, len(files))
    loader = torch.utils.data.DataLoader(ds, batch_size=mb, shuffle=False, num_workers=4)
    opt = torch.optim.AdamW(groups, weight_decay=arm_b.RECIPE['weight_decay'])
    base_lrs = [g['lr'] for g in opt.param_groups]
    weights = torch.tensor(arm_b.class_weights(labels), device='cuda')
    steps = math.ceil(len(files) / 16)
    tr = arm_b._toolkit()
    model.train()
    train_start = time.monotonic()
    losses = []
    iterator = iter(loader)
    for step in range(steps):
        size = min(16, len(files) - step * 16)
        for g, lr in zip(opt.param_groups, base_lrs):
            g['lr'] = lr * tr._schedule(step, steps, arm_b.RECIPE['warmup'])
        opt.zero_grad(set_to_none=True)
        seen, total = 0, 0.0
        while seen < size:
            x, y = next(iterator)
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(x.cuda())
            loss = torch.nn.functional.cross_entropy(logits.float(), y.cuda(), weight=weights, reduction='sum') / size
            loss.backward()
            total += float(loss.detach())
            seen += len(y)
        opt.step()
        losses.append(total)
    torch.cuda.synchronize()
    train_sec = time.monotonic() - train_start
    trainable = {n for n, p in model.named_parameters() if p.requires_grad}
    state = {n: t.detach().cpu().contiguous().clone() for n, t in model.state_dict().items() if n in trainable}
    core.private_mkdir(out, paths.private)
    tmp = checkpoint.with_suffix('.tmp')
    save_file(state, str(tmp))
    tmp.chmod(0o600)
    tmp.replace(checkpoint)
    rec = {'status': 'complete', 'encoder': enc, 'sample_size': sample_size, 'sample_seed': SAMPLE_SEED,
           'sample_sha256': core.sha256_text([str(p.relative_to(paths.root)) + ':' + str(y) for p, y in rows]),
           'manifest_sha256': hashes, 'source_counts': counts, 'sample_class_counts': [labels.count(0), labels.count(1)],
           'recipe': arm_b.RECIPE, 'steps': steps, 'class_weights': arm_b.class_weights(labels),
           'train_seconds': train_sec, 'images_per_second': len(files) / train_sec,
           'estimated_40000_train_hours': 40000 / (len(files) / train_sec) / 3600,
           'peak_vram_gb': torch.cuda.max_memory_allocated() / 2**30,
           'loss_all_finite': bool(np.isfinite(losses).all()), 'checkpoint_sha256': core.sha256_file(checkpoint),
           'total_seconds': time.monotonic() - started, 'code': core.code_revision()}
    if not rec['loss_all_finite']:
        raise ValueError('non-finite transfer loss')
    core.write_private_atomic(marker, json.dumps(rec, indent=2) + '\n')
    del model, adapter
    torch.cuda.empty_cache()
    return rec


def run(enc, k, r, paths=None, force=False, sample_size=40000, steps=None, micro_batch=None):
    import torch
    from safetensors.torch import load_file
    paths = paths or core.Paths.default()
    k = '0' if str(k) == '0' else core.parse_k(k)
    # Keep validation predictions separate as well.
    out = paths.run_dir('H', enc, k, r) if sample_size == 40000 else paths.run_dir('H-validation', enc, k, r)
    if not force and core.is_complete(out):
        existing = json.loads((out / 'run.json').read_text())
        if existing.get('transfer_sample_size') == sample_size:
            return existing
    (out / 'run.json').unlink(missing_ok=True)
    transfer_dir = pretrain_dir(paths, enc, sample_size)
    meta = json.loads((transfer_dir / 'pretrain.json').read_text())
    checkpoint = transfer_dir / 'transfer.safetensors'
    if meta.get('status') != 'complete' or meta['sample_size'] != sample_size or core.sha256_file(checkpoint) != meta['checkpoint_sha256']:
        raise ValueError('invalid transfer checkpoint')
    started = time.monotonic()
    names = sorted(p.name for p in paths.test_png_dir().glob('*.png'))
    if len(names) != core.N_TEST:
        raise ValueError('unexpected number of test PNGs')
    alloc = None if k == '0' else core.load_allocation(paths, k, r)
    seed = arm_b.train_seed(k, r)
    rec = {'arm': 'H', 'encoder': enc, 'k': k, 'r': int(r), 'training_seed': seed,
           'transfer_sha256': meta['checkpoint_sha256'], 'transfer_sample_size': sample_size,
           'recipe': arm_b.RECIPE, 'oof_metrics': None, 'threshold': 0.5,
           'threshold_method': 'fixed_0.5_class_balanced_finetuned'}
    if alloc:
        rec.update(allocation_seed=alloc.seed, allocation_sha256=alloc.sha256,
                   train_image_list_sha256=core.sha256_text(alloc.images), n_train_images=len(alloc.images),
                   n_train_patients=len(alloc.patient_ids))
    if alloc and len(set(alloc.labels.tolist())) < 2:
        prior = float(alloc.labels.mean())
        probs = np.full(len(names), prior)
        rec.update(single_class=True, constant_prior=prior, threshold_method='fixed_0.5_single_class')
    else:
        arm_b.cap_vram()
        model, groups, adapter = arm_b.build_model(enc, 'lora', seed=seed)
        state = load_file(str(checkpoint))
        expected = {n for n, p in model.named_parameters() if p.requires_grad}
        if set(state) != expected:
            raise ValueError('transfer checkpoint parameter mismatch')
        model.load_state_dict(state, strict=False)
        if alloc:
            info = arm_b.train_model(model, groups, enc, arm_b.pool_files(paths, alloc.images), alloc.labels,
                                     seed, steps=steps, micro_batch=micro_batch)
            rec.update(steps=info['steps'], train_seconds=info['seconds'], class_weights=arm_b.class_weights(alloc.labels))
        probs = arm_b.predict_files(model, enc, [paths.test_png_dir() / n for n in names])
        rec.update(single_class=False, peak_vram_gb=torch.cuda.max_memory_allocated() / 2**30)
        del model, adapter
        torch.cuda.empty_cache()
    rec['timings_sec'] = {'total': time.monotonic() - started}
    return core.write_run(paths, out, rec, names, probs)
