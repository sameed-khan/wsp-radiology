"""Supplementary self-reported checkpoint lineage, not an audit guarantee.

``log_checkpoint(path, parents, operation, details)`` appends one JSON line to
``/workspace/output/provenance.jsonl`` (override with ``log_path=`` or the
``WSP_PROVENANCE_LOG`` environment variable) with the SHA-256 of the checkpoint
and, for every parent, its SHA-256 and a per-tensor change summary.
"""
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import torch
from safetensors import safe_open

OPERATIONS = ('gradient_training', 'closed_form_fit', 'composition', 'direct_edit', 'mixed', 'unknown')
DEFAULT_LOG = '/workspace/output/provenance.jsonl'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _clean(value):
    """Make details strictly JSON-serialisable (NaN/inf -> strings, unknown objects -> str)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(v) for v in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if torch.is_tensor(value) and value.numel() == 1:
        return _clean(value.item())
    if hasattr(value, 'item') and getattr(value, 'size', 2) == 1:
        return _clean(value.item())
    return str(value)


def tensor_changes(path, parent_path):
    """Per-tensor summary of ``path`` relative to ``parent_path`` (streamed one tensor at a time)."""
    changes = {}
    with safe_open(str(path), 'pt', device='cpu') as cur, safe_open(str(parent_path), 'pt', device='cpu') as old:
        cur_keys, old_keys = set(cur.keys()), set(old.keys())
        for name in sorted(cur_keys | old_keys):
            if name not in old_keys:
                changes[name] = {'status': 'added', 'shape': list(cur.get_slice(name).get_shape())}
            elif name not in cur_keys:
                changes[name] = {'status': 'removed', 'shape': list(old.get_slice(name).get_shape())}
            else:
                a, b = cur.get_tensor(name), old.get_tensor(name)
                if a.shape != b.shape or a.dtype != b.dtype:
                    changes[name] = {'status': 'shape_changed' if a.shape != b.shape else 'dtype_changed',
                                     'before': list(b.shape), 'after': list(a.shape), 'dtype_before': str(b.dtype), 'dtype_after': str(a.dtype)}
                    continue
                neq = a != b
                entry = {'status': 'compared', 'changed': int(neq.sum()), 'numel': a.numel(), 'max_abs_delta': 0.0, 'mean_abs_delta': 0.0, 'relative_change': 0.0}
                if entry['changed'] and a.numel():
                    if a.dtype == torch.bool:
                        a, b = a.to(torch.uint8), b.to(torch.uint8)
                    d = (a.to(torch.float64) - b.to(torch.float64)).abs()
                    entry['max_abs_delta'] = float(d.max())
                    entry['mean_abs_delta'] = float(d.mean())
                    denom = float(b.to(torch.float64).norm())
                    entry['relative_change'] = float(d.square().sum().sqrt()) / denom if denom > 0 else float('inf')
                    if not math.isfinite(entry['relative_change']):
                        entry['relative_change'] = None
                changes[name] = entry
    return changes


def log_checkpoint(path, parents, operation, details, log_path=None):
    if operation not in OPERATIONS:
        raise ValueError(f'operation must be one of {list(OPERATIONS)}')
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    ancestry = []
    for parent in parents or []:
        parent = Path(parent)
        if not parent.is_file():
            raise FileNotFoundError(f'parent checkpoint not found: {parent}')
        ancestry.append({'path': str(parent), 'sha256': sha256(parent), 'tensors': tensor_changes(path, parent)})
    with safe_open(str(path), 'pt', device='cpu') as f:
        names = list(f.keys())
    entry = {'time': datetime.now(timezone.utc).isoformat(), 'path': str(path), 'sha256': sha256(path),
             'num_tensors': len(names), 'parents': ancestry, 'operation': operation, 'details': _clean(details or {})}
    log_path = Path(log_path or os.environ.get('WSP_PROVENANCE_LOG', DEFAULT_LOG))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, allow_nan=False) + '\n')
        f.flush()
        os.fsync(f.fileno())
    return entry
