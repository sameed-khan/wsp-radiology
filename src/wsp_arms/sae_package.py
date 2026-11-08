"""Build the label-free SAE distribution; inputs are an explicit allowlist only."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import numpy as np

from . import core, sae_train


def copy_pool_artifact(source, destination, filename):
    """Only these label-free artifacts may cross the private-data boundary."""
    assert filename in {'sae.safetensors', 'norm.json'} and 'test' not in filename.lower()
    shutil.copyfile(source / filename, destination / filename)


def build(root=None, package_id='phase1'):
    import torch
    paths = core.Paths(Path(root)) if root else core.Paths.default()
    if not package_id or Path(package_id).name != package_id or package_id in ('.', '..', 'current'):
        raise ValueError('invalid package id')
    base = paths.root / 'data/agent-sae'
    out = base / package_id
    if out.exists():
        raise FileExistsError(out)
    core.private_mkdir(out, None)
    pool = paths.root / 'data/agent-pool/current'
    names = sorted(p.name for p in pool.glob('*.png'))
    if len(names) != 2993:
        raise ValueError('unexpected sanitized pool size')
    (out / 'pool_images.txt').write_text('\n'.join(names) + '\n')
    specs = [('skelex', i) for i in (8, 12, 16, 20)] + [('medsiglip', 18), ('dinov3', 16)]
    # Layers for reused models are verified against their actual receipts below.
    torch.cuda.set_per_process_memory_fraction(5.8 / 24.0)
    from wsp_ml.encoders import load_encoder
    tk = sae_train._toolkit()
    for enc, layer in specs:
        source = (paths.root / 'data/agent-sae-training' / enc / f'L{layer}' if enc == 'skelex' and layer != 16
                  else sae_train.sae_dir(paths, enc))
        rec = json.loads((source / 'sae.json').read_text())
        cfg = rec['config']
        if (rec['encoder'], rec['layer'], cfg['steps'], cfg['topk'], cfg['dict_mult'], cfg['batch_tokens'], cfg['lr']) != (enc, layer, 20000, 32, 8, 2048, 1e-4):
            raise ValueError('SAE receipt does not match the required recipe')
        idx = json.loads((paths.pool_features(enc) / 'index.json').read_text())['filenames']
        if len(idx) != len(names) or set(idx) != set(names):
            raise ValueError('pool index mismatch')
        if rec['pool_names_sha256'] != core.sha256_text(idx):
            raise ValueError('SAE pool order differs from feature index')
        d = out / enc / f'L{layer}'
        core.private_mkdir(d, None)
        # Never copy a directory or receipt wholesale: these contain test-derived data.
        for filename in ('sae.safetensors', 'norm.json'):
            copy_pool_artifact(source, d, filename)
        old = np.load(source / 'pool_mean_latents.npy', mmap_mode='r', allow_pickle=False)
        if old.shape != (len(names), rec['dictionary_size']):
            raise ValueError('latent shape mismatch')
        lookup = {n: i for i, n in enumerate(idx)}
        np.save(d / 'pool_mean_latents.npy', np.asarray(old[[lookup[n] for n in names]], dtype=np.float16), allow_pickle=False)
        norm = json.loads((d / 'norm.json').read_text())
        model = tk.load_sae(d / 'sae.safetensors', rec['hidden_size'], rec['dictionary_size'], cfg['topk']).cuda()
        adapter = load_encoder(enc, 'cuda', torch.float32)
        mu = torch.tensor(norm['mean'], device='cuda', dtype=torch.float32)
        freq = torch.zeros(rec['dictionary_size'], device='cuda')
        se = var = count = 0
        with torch.no_grad():
            for t in sae_train._token_batches(adapter, [pool / n for n in names], layer, batch=2):
                x = (t.reshape(-1, rec['hidden_size']) - mu) / norm['scale']
                a = model.encode(x)
                freq += (a > 0).sum(0)
                se += float((model.decoder(a) - x).square().sum())
                var += float(x.square().sum())
                count += x.shape[0]
        quality = {'explained_variance_pool_tokens': 1 - se / var, 'dead_latent_fraction_pool': float((freq == 0).float().mean()), 'mean_l0': float(freq.sum() / count)}
        metadata = {'encoder': enc, 'layer': layer, 'token_type': 'patch', 'hidden_size': rec['hidden_size'], 'dictionary_size': rec['dictionary_size'], 'k': cfg['topk'], 'steps': cfg['steps'], 'lr': cfg['lr'], 'seed': cfg['seed'], 'normalization': cfg['input_norm']}
        (d / 'quality.json').write_text(json.dumps(quality, indent=2) + '\n')
        (d / 'sae.json').write_text(json.dumps(metadata, indent=2) + '\n')
        del model, adapter
        torch.cuda.empty_cache()
        print(f'{enc} L{layer}: {quality}', flush=True)
    (out / 'README.md').write_text('''# Pool sparse autoencoders\n\nEach encoder/layer directory contains SAE weights, metadata, normalization, pool-only quality metrics, and float16 per-image mean latent activations. Rows correspond to `pool_images.txt`. Inputs must be patch tokens centered and scaled using `norm.json`. These SAEs were trained without labels.\n\n```python\nimport json\nfrom pathlib import Path\nfrom wsp_toolkit.sae import load_sae\np = Path('/workspace/provided/sae/skelex/L16')\nmeta = json.loads((p / 'sae.json').read_text())\nsae = load_sae(p / 'sae.safetensors', meta['hidden_size'], meta['dictionary_size'], meta['k'])\n```\n''')
    files = sorted(p for p in out.rglob('*') if p.is_file())
    assert all('test' not in str(p.relative_to(out)).lower() for p in files)
    manifest = {str(p.relative_to(out)): core.sha256_file(p) for p in files}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    for p in out.rglob('*'):
        os.chmod(p, 0o700 if p.is_dir() else 0o600)
    link = base / 'current'
    tmp = base / '.current.tmp'
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(package_id)
    os.replace(tmp, link)
    return out


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--id', default='phase1')
    args = p.parse_args()
    print(build(package_id=args.id))
