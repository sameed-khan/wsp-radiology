"""Public-image pHash cache and private overlap comparison."""
import json
import multiprocessing as mp
from pathlib import Path

import imagehash
import numpy as np
from wsp_prep.core import load_image_bytes

CACHE = Path('/home/skhanxx8/projects/wsp-radiology/features/phash')
EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}


def _hash(path):
    try:
        return str(path), str(imagehash.phash(load_image_bytes(Path(path).read_bytes()))), None
    except Exception as exc:
        return str(path), None, str(exc)


def overlap(roots, out, manifest=None, workers=12):
    if not 1 <= workers <= 12:
        raise ValueError('workers must be between 1 and 12')
    CACHE.mkdir(parents=True, exist_ok=True)
    import hashlib
    all_hashes = []
    failures = []
    for root in roots:
        root = Path(root).resolve()
        if not root.is_dir():
            raise ValueError(f'Not a directory: {root}')
        key = hashlib.sha256(str(root).encode()).hexdigest()[:16]
        cache = CACHE / f'{key}.json'
        cached = json.loads(cache.read_text()) if cache.exists() else {}
        old = cached.get('files', {}) if cached.get('version') == 2 else {}
        if not isinstance(old, dict): old = {}
        files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS)
        current = {}
        pending = []
        for p in files:
            stat = p.stat()
            signature = [stat.st_size, stat.st_mtime_ns]
            item = old.get(str(p))
            if item and item[:2] == signature:
                current[str(p)] = item
            else:
                pending.append((p, signature))
        signatures = {str(p): s for p, s in pending}
        with mp.Pool(workers) as pool:
            for path, value, error in pool.imap_unordered(_hash, (p for p, _ in pending), chunksize=32):
                if error:
                    failures.append({'path': path, 'error': error})
                else:
                    current[path] = signatures[path] + [value]
        cache.write_text(json.dumps({'version': 2, 'files': current}))
        all_hashes.extend((path, int(item[2], 16)) for path, item in current.items())
        print(f'{root.name}: {len(current)} hashed, {len(pending)} computed, {len(failures)} failures', flush=True)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    report = {'external_images': len(all_hashes), 'hash_failures': len(failures), 'comparison': 'pending', 'audit_complete': False}
    if manifest is not None and Path(manifest).exists():
        records = json.loads(Path(manifest).read_text())
        hashes = np.array([h for _, h in all_hashes], dtype=np.uint64)
        pairs, minima = [], []
        lookup = np.array([i.bit_count() for i in range(256)], dtype=np.uint8)
        for record in records:
            distances = lookup[np.bitwise_xor(hashes, np.uint64(int(record['phash'], 16))).view(np.uint8).reshape(-1, 8)].sum(axis=1)
            minimum = int(distances.min()) if len(distances) else None
            minima.append(minimum)
            for idx in np.flatnonzero(distances <= 6):
                pairs.append({'file': record['file'], 'external': all_hashes[int(idx)][0], 'distance': int(distances[idx])})
        report.update(comparison='complete', audit_complete=bool(all_hashes) and not failures and bool(records), min_distance_counts={str(i): minima.count(i) for i in sorted(set(minima)) if i is not None}, pair_counts_by_distance={str(i): sum(p['distance'] == i for p in pairs) for i in range(7)})
        path = out / 'pairs.json'
        path.write_text(json.dumps(pairs))
        path.chmod(0o600)
    (CACHE / 'hash-failures.json').write_text(json.dumps(failures, indent=2))
    (out / 'overlap-summary.json').write_text(json.dumps(report, indent=2))
    return report
