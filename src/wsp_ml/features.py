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
from .encoders import MODELS, load_encoder, model_path
from .external import external_manifest


def image_paths(dataset):
    if dataset == 'pool':
        return sorted((ROOT / 'data/pool').glob('*.png')), ROOT / 'features'
    if dataset == 'test':
        return sorted((PRIVATE / 'test-png').glob('*.png')), PRIVATE / 'features'
    if dataset in ('external:FracAtlas', 'external:GRAZPEDWRI-DX', 'external:MURA'):
        paths, _, _ = external_manifest(ROOT / 'data/external/extracted', dataset.split(':', 1)[1])
        return paths, ROOT / 'features'
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
    model_dir = model_path(encoder).resolve()
    model_hashes = {p.name: digest(p, 'sha256') for p in sorted(model_dir.glob('*.safetensors'))}
    if not model_hashes:
        raise ValueError('no model weight files to hash')
    adapter = load_encoder(encoder, 'cuda', torch.float32, path=model_dir)
    check = paths[:8]
    a, b = run_batch(adapter, check), run_batch(adapter, check)
    if a.keys() != b.keys() or any(not np.isfinite(v).all() for values in (a, b) for v in values.values()):
        raise ValueError('non-finite or inconsistent determinism outputs')
    difference = max(float(np.max(np.abs(a[k] - b[k]))) for k in a)
    if not np.isfinite(difference) or not difference < 1e-2:
        raise ValueError('determinism check failed')
    out = base / encoder / (('external/' + dataset.split(':', 1)[1]) if dataset.startswith('external:') else dataset)
    if limit is not None:
        out = out / f'limit-{limit}'
    if dataset == 'test':
        for directory in (PRIVATE / 'features', PRIVATE / 'features' / encoder, PRIVATE / 'features' / encoder / 'test', out):
            private_dir(directory)
    else:
        out.mkdir(parents=True, exist_ok=True)
    arrays = {}
    for start in range(0, len(paths), 4):
        values = run_batch(adapter, paths[start:start+4])
        if any(not np.isfinite(value).all() for value in values.values()):
            raise ValueError('non-finite feature batch')
        for key, value in values.items():
            arrays.setdefault(key, []).append(value)
    for key, batches in arrays.items():
        path = out / f'{key}.npy'
        np.save(path, np.concatenate(batches))
        if dataset == 'test': os.chmod(path, 0o600)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    index = {'filenames': [str(p.relative_to(paths[0].parent)) if dataset in ('pool','test') else str(p.relative_to(ROOT / 'data/external/extracted')) for p in paths], 'model_sha256': model_hashes, 'code_revision': revision, 'dtype': 'float32', 'autocast': 'bfloat16', 'layers': adapter.layer_indices_default, 'cls_available': {str(i): ('map_pool' if encoder == 'medsiglip' and i == adapter.num_layers else False if encoder == 'medsiglip' else True) for i in adapter.layer_indices_default}, 'determinism_max_abs_diff': difference}
    if dataset.startswith('external:'):
        _, entries, counts = external_manifest(ROOT / 'data/external/extracted', dataset.split(':', 1)[1])
        index['labels'] = entries[:len(paths)]
        index['label_counts'] = {'images': len(index['labels']), 'negative': sum(e['label'] == 0 for e in index['labels']), 'positive': sum(e['label'] == 1 for e in index['labels'])}
        index['source_label_counts'] = counts
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


def audit_features():
    """Sanitized audit of the six real feature sets; no filenames or labels are emitted."""
    from .encoders import MODELS as M
    report, problems = {}, []
    for enc in M:
        expected = {p.name: digest(p, 'sha256') for p in sorted(model_path(enc).resolve().glob('*.safetensors'))}
        for ds, base in (('pool', ROOT / 'features'), ('test', PRIVATE / 'features')):
            d = base / enc / ds
            entry = {'dir_mode': oct(d.stat().st_mode & 0o777)}
            index = json.loads((d / 'index.json').read_text())
            n = len(index['filenames'])
            entry.update(images=n, unique_filenames=len(set(index['filenames'])) == n, model_hashes_match=index['model_sha256'] == expected and bool(expected),
                         code_revision=index['code_revision'], determinism_max_abs_diff=index['determinism_max_abs_diff'], arrays={}, file_modes={})
            entry['file_modes']['index.json'] = oct((d / 'index.json').stat().st_mode & 0o777)
            expected_keys = ['pooled'] + [f'patch_mean-{i}' for i in index['layers']] + [f'cls-{i}' for i in index['layers'] if index['cls_available'][str(i)]]
            entry['unexpected_or_missing_arrays'] = sorted(set(p.stem for p in d.glob('*.npy')) ^ set(expected_keys))
            for key in expected_keys:
                a = np.load(d / f'{key}.npy')
                entry['arrays'][key] = {'shape': list(a.shape), 'dtype': str(a.dtype), 'finite': bool(np.isfinite(a).all()), 'rows_match': a.shape[0] == n}
                entry['file_modes'][f'{key}.npy'] = oct((d / f'{key}.npy').stat().st_mode & 0o777)
            if entry['unexpected_or_missing_arrays'] or not entry['unique_filenames'] or not entry['model_hashes_match'] or any(not v['finite'] or not v['rows_match'] for v in entry['arrays'].values()):
                problems.append(f'{enc}/{ds}')
            if ds == 'test' and (entry['dir_mode'] != '0o700' or any(m != '0o600' for m in entry['file_modes'].values())):
                problems.append(f'{enc}/{ds} modes')
            report[f'{enc}/{ds}'] = entry
    report['problems'] = problems
    return report
