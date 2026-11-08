"""Arm E, part 1: one top-k SAE per encoder on pool patch tokens at the 2/3-depth layer (no labels).

Streams patch tokens (GPU, bf16 autocast) into an fp16 on-disk memmap (scratch, deleted afterwards),
trains the SAE from random token batches, then writes per-image mean SAE latents for all pool images and
all test images (test images are read only to compute features; no test labels are touched).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from . import core

SAE_CFG = dict(dict_mult=8, topk=32, steps=20000, lr=1e-4, batch_tokens=2048, seed=7, input_norm='center + global scale to unit per-dim rms',
               decoder_init='unit-norm columns, encoder = decoder^T (tied init)', vram_cap_gb=8)


def _toolkit():
    try:
        import wsp_toolkit  # noqa: F401
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'toolkit'))
    from wsp_toolkit import sae as tk_sae
    return tk_sae


def sae_dir(paths, enc):
    return paths.private / 'runs/baselines/E' / enc / 'sae'


def target_layer(num_layers):
    return round(num_layers * 4 / 6)


def sae_complete(paths, enc):
    return (sae_dir(paths, enc) / 'sae.json').exists()


class _Imgs:
    def __init__(self, name, files):
        self.name, self.files = name, files

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        from PIL import Image
        from wsp_ml.encoders import preprocess
        with Image.open(self.files[i]) as im:
            return preprocess(im, self.name)


def _token_batches(adapter, files, layer, batch=16):
    import torch
    loader = torch.utils.data.DataLoader(_Imgs(adapter.name, files), batch_size=batch, num_workers=4, shuffle=False)
    for x in loader:
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            t = adapter.forward(x.to('cuda'), layers=[layer])['patch_tokens'][layer]
        yield t.float()


def train_one(enc, paths=None, steps=None, limit=None, force=False, out_dir=None, log=print, layer=None, pool_only=False):
    import torch
    paths = paths or core.Paths.default()
    tk = _toolkit()
    from wsp_ml.encoders import load_encoder
    out = Path(out_dir) if out_dir else sae_dir(paths, enc)
    if (out / 'sae.json').exists() and not force:
        log(f'{enc}: SAE already complete')
        return json.loads((out / 'sae.json').read_text())
    core.private_mkdir(out, None)
    steps = steps or SAE_CFG['steps']
    torch.cuda.set_per_process_memory_fraction(5.8 / 24.0 if pool_only else SAE_CFG['vram_cap_gb'] / 24.0)
    torch.cuda.reset_peak_memory_stats()
    t0 = time.monotonic()
    pool_idx = json.loads((paths.pool_features(enc) / 'index.json').read_text())
    pool_names = pool_idx['filenames'][:limit] if limit else pool_idx['filenames']
    test_names = []
    if not pool_only:
        test_names = sorted(p.name for p in paths.test_png_dir().glob('*.png'))
        if limit:
            test_names = test_names[:limit]
        elif len(test_names) != core.N_TEST:
            raise ValueError('unexpected number of test PNGs')
        if not limit and json.loads((paths.test_features(enc) / 'index.json').read_text())['filenames'] != test_names:
            raise ValueError('test feature index != test png listing')
    adapter = load_encoder(enc, 'cuda', torch.float32)
    layer = target_layer(adapter.num_layers) if layer is None else layer
    if not 1 <= layer <= adapter.num_layers:
        raise ValueError('layer outside encoder depth')
    D = adapter.hidden_size
    pool_files = [paths.root / 'data/pool' / n for n in pool_names]
    test_files = [paths.test_png_dir() / n for n in test_names]

    # ---- 1. stream pool tokens to fp16 memmap
    mm_path = out / 'tokens.f16.tmp'
    mm = None
    P = None
    row = 0
    n_imgs = len(pool_files)
    absmax = 0.0
    for t in _token_batches(adapter, pool_files, layer):
        if mm is None:
            P = t.shape[1]
            mm = np.lib.format.open_memmap(mm_path, mode='w+', dtype=np.float16, shape=(n_imgs * P, D))
        a = t.reshape(-1, D)
        absmax = max(absmax, float(a.abs().max()))
        if absmax > 60000:
            raise ValueError('activations exceed fp16 range')
        mm[row:row + a.shape[0]] = a.half().cpu().numpy()
        row += a.shape[0]
    assert row == n_imgs * P
    mm.flush()
    t_extract = time.monotonic() - t0

    # ---- 2. normalization stats (streamed)
    s1 = np.zeros(D, np.float64)
    for i in range(0, row, 200000):
        s1 += mm[i:i + 200000].astype(np.float64).sum(0)
    mu = (s1 / row)
    ss = 0.0
    for i in range(0, row, 200000):
        ss += float(((mm[i:i + 200000].astype(np.float64) - mu) ** 2).sum())
    scale = float(np.sqrt(ss / (row * D)))  # per-dim rms after centering
    mu_t = torch.tensor(mu, dtype=torch.float32, device='cuda')

    def norm(x):
        return (x - mu_t) / scale

    # ---- 3. train
    torch.manual_seed(SAE_CFG['seed'])
    gen = np.random.default_rng(SAE_CFG['seed'])
    model = tk.TopKSAE(D, SAE_CFG['dict_mult'] * D, SAE_CFG['topk'])
    with torch.no_grad():
        w = torch.randn(D, SAE_CFG['dict_mult'] * D)
        w = w / w.norm(dim=0, keepdim=True)
        model.decoder.weight.copy_(w)
        model.encoder.weight.copy_(w.T)
        model.encoder.bias.zero_()
        model.decoder.bias.zero_()
    B = SAE_CFG['batch_tokens']

    class Batches:
        def __iter__(self):
            while True:
                idx = np.sort(gen.integers(0, row, size=B))
                yield norm(torch.from_numpy(mm[idx]).to('cuda').float())

    t1 = time.monotonic()
    ckpt_dir = out / 'ckpt'
    losses = tk.train_sae(model, Batches(), steps=steps, lr=SAE_CFG['lr'], device='cuda',
                                                     checkpoint=ckpt_dir, every=max(1, steps // 4) if steps < 4000 else 5000,
                                                     log_path=out / 'provenance.jsonl')
    t_train = time.monotonic() - t1
    model.eval()

    # ---- 4. mean latents (pool from memmap, test streamed) + diagnostics
    nl = model.encoder.out_features
    freq = torch.zeros(nl, device='cuda')
    pool_mean = np.zeros((n_imgs, nl), np.float32)
    var_tot = 0.0
    se_pool = 0.0
    with torch.no_grad():
        for i in range(n_imgs):
            x = norm(torch.from_numpy(mm[i * P:(i + 1) * P]).to('cuda').float())
            a = model.encode(x)
            pool_mean[i] = a.mean(0).cpu().numpy()
            freq += (a > 0).float().sum(0)
            se_pool += float((model.decoder(a) - x).square().sum())
            var_tot += float(x.square().sum())
    n_pool_tok = n_imgs * P
    dead_pool = float((freq == 0).float().mean())
    ev_pool = 1 - se_pool / var_tot
    test_mean = np.zeros((len(test_files), nl), np.float32)
    se_t = var_t = 0.0
    row_t = 0
    with torch.no_grad():
        for t in _token_batches(adapter, test_files, layer):
            for j in range(t.shape[0]):
                x = norm(t[j])
                a = model.encode(x)
                test_mean[row_t] = a.mean(0).cpu().numpy()
                se_t += float((model.decoder(a) - x).square().sum())
                var_t += float(x.square().sum())
                row_t += 1
    ev_test = 1 - se_t / var_t if var_t else None
    peak = torch.cuda.max_memory_allocated()
    mm_del = mm_path
    del mm
    mm_del.unlink()

    # ---- 5. write
    from safetensors.torch import save_file
    core.write_private_atomic(out / 'pool_mean_latents.npy', _npy_bytes(pool_mean))
    if not pool_only:
        core.write_private_atomic(out / 'test_mean_latents.npy', _npy_bytes(test_mean))
    sd = {k: v.detach().cpu().contiguous() for k, v in model.state_dict().items()}
    tmp = out / 'sae.safetensors.tmp'
    save_file(sd, str(tmp))
    core.write_private_atomic(out / 'sae.safetensors', tmp.read_bytes())
    tmp.unlink()
    core.write_private_atomic(out / 'norm.json', json.dumps({'mean': mu.tolist(), 'scale': scale}))
    ls = np.array(losses)
    rec = {
        'encoder': enc, 'layer': layer, 'num_layers': adapter.num_layers, 'hidden_size': D, 'tokens_per_image': P,
        'dictionary_size': nl, 'config': dict(SAE_CFG, steps=steps), 'n_pool_images': n_imgs, 'n_pool_tokens': n_pool_tok,
        'n_test_images': len(test_files), 'pool_index_sha256': core.sha256_file(paths.pool_features(enc) / 'index.json'),
        'pool_names_sha256': core.sha256_text(pool_names), 'test_names_sha256': core.sha256_text(test_names),
        'tokens_absmax': absmax, 'norm_scale': scale,
        'loss_first100_mean': float(ls[:100].mean()), 'loss_last100_mean': float(ls[-100:].mean()),
        'loss_every_500': [float(x) for x in ls[::500]],
        'explained_variance_pool_tokens': ev_pool, 'explained_variance_test_tokens': ev_test,
        'dead_latent_fraction_pool': dead_pool, 'mean_l0_pool': float(freq.sum() / n_pool_tok),
        'peak_gpu_bytes': int(peak), 'timings_sec': {'extract': t_extract, 'train': t_train, 'total': time.monotonic() - t0},
        'model_sha256': pool_idx.get('model_sha256'), 'code': core.code_revision(),
        'sae_sha256': core.sha256_file(out / 'sae.safetensors'),
        'note': 'SAE trained on pool patch tokens only (no labels). explained_variance_test_tokens is a label-free generalization diagnostic.',
    }
    import shutil
    shutil.rmtree(ckpt_dir, ignore_errors=True)
    core.write_private_atomic(out / 'sae.json', json.dumps(rec, indent=2, sort_keys=True) + '\n')
    log(f'{enc}: layer {layer} dead={dead_pool:.3f} EV pool={ev_pool:.3f} test={ev_test} peak={peak/2**30:.2f}GiB train={t_train:.0f}s')
    return rec


def _npy_bytes(a):
    import io
    b = io.BytesIO()
    np.save(b, a)
    return b.getvalue()
