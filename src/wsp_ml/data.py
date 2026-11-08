from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import secrets
import zipfile
from pathlib import Path

import numpy as np
from wsp_prep.core import check_mfxr, digest, load_image_bytes, validate_patient_map

ROOT = Path('/home/skhanxx8/projects/wsp-radiology')
PRIVATE = ROOT / 'data/locked/private'


def private_dir(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    current = path
    while current == PRIVATE or PRIVATE in current.parents:
        os.chmod(current, 0o700)
        if current == PRIVATE:
            break
        current = current.parent
    return path


def write_private(path, data):
    private_dir(path.parent)
    raw = data if isinstance(data, bytes) else data.encode()
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f'refusing to overwrite differing output: {path}')
        os.chmod(path, 0o600)
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw)


def json_bytes(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + '\n'


def inventory_paths():
    generation = (ROOT / 'data/pool').resolve().parents[1]
    return generation / 'data/locked/inventory.json', generation / 'data/locked/prefix-map-proposal.json'


def patient_map():
    inventory_path, proposal_path = inventory_paths()
    inv = json.loads(inventory_path.read_text())
    proposal = json.loads(proposal_path.read_text())
    values = {}
    for row in inv['records']:
        pair = (row['split'], row['label'])
        if row['patient_prefix'] in values and values[row['patient_prefix']] != pair:
            raise ValueError('conflicting patient information')
        values[row['patient_prefix']] = pair
    if {r['source_prefix'] for r in proposal} != set(values):
        raise ValueError('proposal and inventory differ')
    rows = [dict(source_prefix=p, patient_id='P'+p, split=values[p][0], label=values[p][1], reviewed=True) for p in sorted(values)]
    path = PRIVATE / 'patient-map-reviewed.json'
    write_private(path, json_bytes(rows))
    result = validate_patient_map(path, inventory_path)
    if len(rows) != 1484 or sum(r['split']=='train' for r in rows) != 993:
        raise ValueError('unexpected patient count')
    return result


def seed_for(k, r):
    return int(hashlib.sha256(f'wsp-phase1|mfxr|k={k}|r={r}'.encode()).hexdigest()[:16], 16)


def allocation(records, patients, k, r):
    seed = seed_for(k, r)
    ids = sorted(patients)
    chosen = ids if k == 'all' else sorted(np.random.default_rng(seed).choice(ids, size=int(k), replace=False).tolist())
    selected = set(chosen)
    images = [dict(anonymous_filename=x['anonymous_filename'], patient_id='P'+x['patient_prefix'], label=int(x['label']=='anomaly')) for x in records if x['split']=='train' and 'P'+x['patient_prefix'] in selected]
    images.sort(key=lambda x: x['anonymous_filename'])
    return {'seed': seed, 'patient_ids': chosen, 'images': images}


def sample():
    inventory_path, _ = inventory_paths()
    validate_patient_map(PRIVATE / 'patient-map-reviewed.json', inventory_path)
    records = json.loads(inventory_path.read_text())['records']
    rows = json.loads((PRIVATE / 'patient-map-reviewed.json').read_text())
    patients = [r['patient_id'] for r in rows if r['split']=='train']
    summary = []
    for k in (10, 20, 50, 100, 250, 'all'):
        for r in range(1, 6):
            data = allocation(records, patients, k, r)
            path = PRIVATE / 'allocations' / f'k{k}' / f'r{r}'
            write_private(path / 'allocation.json', json_bytes(data))
            out = io.StringIO(newline='')
            writer = csv.writer(out, lineterminator='\n')
            writer.writerow(['image', 'patient', 'label'])
            for x in data['images']:
                token = hashlib.sha256(f"{data['seed']}|{x['patient_id']}".encode()).hexdigest()[:12]
                writer.writerow([x['anonymous_filename'], token, x['label']])
            write_private(path / 'labels.csv', out.getvalue())
            summary.append({'k': k, 'r': r, 'n_patients': len(data['patient_ids']), 'n_images': len(data['images']), 'sha256': digest(path / 'allocation.json', 'sha256'), 'seed_sha256': hashlib.sha256(str(data['seed']).encode()).hexdigest()})
    return summary


def hash_corpus():
    inv = json.loads(inventory_paths()[0].read_text())
    records = inv['records']
    corpus = {'archive_sha256': inv['archive_sha256'], 'raw_sha256': [r['raw_sha256'] for r in records], 'normalized_sha256': [r['normalized_sha256'] for r in records], 'phash': {'pool': [r['phash'] for r in records if r['split']=='train'], 'test': [r['phash'] for r in records if r['split']=='test']}, 'basenames': sorted({Path(r['source_path']).name for r in records})}
    write_private(PRIVATE / 'hash-corpus.json', json_bytes(corpus))
    return {'images': len(records), 'sha256': digest(PRIVATE / 'hash-corpus.json', 'sha256')}


def test_images():
    inv = json.loads(inventory_paths()[0].read_text())
    archive = ROOT / 'data/locked/downloads/MFXR.zip'
    check_mfxr(archive)
    manifest_path = PRIVATE / 'test-manifest.json'
    if manifest_path.exists():
        rows = json.loads(manifest_path.read_text())
        if len(rows) != 1593 or any(digest(PRIVATE / 'test-png' / r['file'], 'sha256') != r['sha256'] for r in rows):
            raise ValueError('existing test materialization is inconsistent')
        return {'images': len(rows), 'sha256': digest(manifest_path, 'sha256')}
    outdir = private_dir(PRIVATE / 'test-png')
    if any(outdir.iterdir()):
        raise ValueError('test image directory is nonempty without manifest')
    rows = []
    with zipfile.ZipFile(archive) as z:
        for record in inv['records']:
            if record['split'] != 'test':
                continue
            data = z.read(record['source_path'])
            if hashlib.sha256(data).hexdigest() != record['raw_sha256']:
                raise ValueError('archive image hash mismatch')
            buf = io.BytesIO()
            load_image_bytes(data).save(buf, format='PNG', optimize=False)
            raw = buf.getvalue()
            sha = hashlib.sha256(raw).hexdigest()
            if sha != record['normalized_sha256']:
                raise ValueError('normalized image hash mismatch')
            name = secrets.token_hex(16) + '.png'
            write_private(outdir / name, raw)
            rows.append({'file': name, 'patient_id': 'P'+record['patient_prefix'], 'label': int(record['label']=='anomaly'), 'source_path': record['source_path'], 'phash': record['phash'], 'sha256': sha})
    if len(rows) != 1593:
        raise ValueError('unexpected test image count')
    write_private(manifest_path, json_bytes(rows))
    return {'images': len(rows), 'sha256': digest(manifest_path, 'sha256')}
