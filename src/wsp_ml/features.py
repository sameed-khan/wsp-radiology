from __future__ import annotations
import hashlib
import json
import os
import subprocess
from pathlib import Path
import numpy as np
import torch
from PIL import Image
from .data import ROOT, PRIVATE, digest, private_dir
from .encoders import MODELS, load_encoder


def image_paths(dataset):
    if dataset == 'pool':
        return sorted((ROOT / 'data/pool').glob('*.png')), ROOT / 'features'
    if dataset == 'test':
        return sorted((PRIVATE / 'test-png').glob('*.png')), PRIVATE / 'features'
    if dataset in ('external:FracAtlas', 'external:GRAZPEDWRI-DX', 'external:MURA'):
        name = dataset.split(':', 1)[1]
        base = ROOT / 'data/external/extracted' / name
        return sorted(p for p in base.rglob('*') if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp')), ROOT / 'features'
    raise ValueError('invalid dataset')


def run_batch(adapter, paths):
    tensors = []
    for path in paths:
        with Image.open(path) as im:
            tensors.append(adapter.preprocess(im))
    x = torch.stack(tensors).to('cuda')
    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
        result = adapter.forward(x)
    return {**{'pooled': result['pooled'].float().cpu().numpy()}, **{f'{kind}-{layer}': value.float().cpu().numpy() for kind in ('cls', 'patch_mean') for layer, value in result[kind].items()}}


def extract(encoder, dataset, limit):
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required')
    paths, base = image_paths(dataset)
    if limit is not None:
        if limit < 1:
            raise ValueError('limit must be positive')
        paths = paths[:limit]
    if not paths:
        raise ValueError('no images')
    adapter = load_encoder(encoder, 'cuda', torch.float32)
    check = paths[:8]
    a, b = run_batch(adapter, check), run_batch(adapter, check)
    difference = max(float(np.max(np.abs(a[k] - b[k]))) for k in a)
    if difference >= 1e-2:
        raise ValueError('determinism check failed')
    out = base / encoder / (('external/' + dataset.split(':', 1)[1]) if dataset.startswith('external:') else dataset)
    if dataset == 'test':
        for directory in (PRIVATE / 'features', PRIVATE / 'features' / encoder, out):
            private_dir(directory)
    else:
        out.mkdir(parents=True, exist_ok=True)
    arrays = {}
    for start in range(0, len(paths), 4):
        values = run_batch(adapter, paths[start:start+4])
        for key, value in values.items():
            arrays.setdefault(key, []).append(value)
    for key, batches in arrays.items():
        path = out / f'{key}.npy'
        np.save(path, np.concatenate(batches))
        if dataset == 'test': os.chmod(path, 0o600)
    model_dir = ROOT / 'models' / MODELS[encoder]
    model_hashes = {p.name: digest(p, 'sha256') for p in sorted(model_dir.glob('*.safetensors'))}
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    index = {'filenames': [str(p.relative_to(paths[0].parent)) if dataset in ('pool','test') else str(p.relative_to(ROOT / 'data/external/extracted')) for p in paths], 'model_sha256': model_hashes, 'code_revision': revision, 'dtype': 'float32', 'autocast': 'bfloat16', 'layers': adapter.layer_indices_default, 'cls_available': {str(i): ('map_pool' if encoder == 'medsiglip' and i == adapter.num_layers else False if encoder == 'medsiglip' else True) for i in adapter.layer_indices_default}, 'determinism_max_abs_diff': difference}
    (out / 'index.json').write_text(json.dumps(index, indent=2)+'\n')
    if dataset == 'test': os.chmod(out / 'index.json', 0o600)
    return {'encoder': encoder, 'set': dataset, 'images': len(paths), 'determinism_max_abs_diff': difference, 'output': str(out), 'peak_gpu_bytes': torch.cuda.max_memory_allocated()}


def cuda_smoke():
    if not torch.cuda.is_available(): raise RuntimeError('CUDA unavailable')
    torch.manual_seed(7)
    a = torch.randn(64, 64)
    diff = (a @ a - (a.cuda() @ a.cuda()).cpu()).abs().max().item()
    if diff > 1e-3: raise ValueError('GPU matmul differs')
    paths, _ = image_paths('pool')
    outputs = {}
    for name in MODELS:
        adapter = load_encoder(name, 'cuda', torch.float32)
        value = run_batch(adapter, paths[:1])
        outputs[name] = {'shape': list(value['pooled'].shape), 'finite': bool(np.isfinite(value['pooled']).all())}
        if not outputs[name]['finite']: raise ValueError('non-finite output')
        del adapter
        torch.cuda.empty_cache()
    return {'torch': torch.__version__, 'cuda': torch.version.cuda, 'cudnn': torch.backends.cudnn.version(), 'matmul_max_abs_diff': diff, 'encoders': outputs, 'peak_gpu_bytes': torch.cuda.max_memory_allocated()}
