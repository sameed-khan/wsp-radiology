import hashlib
import json
import re
import numpy as np
import pytest
from wsp_ml.data import allocation, seed_for, hash_corpus


def test_sampler_seed_and_integrity():
    rows = [dict(split='train', patient_prefix=str(i), anonymous_filename=f'{i}-{j}.png', label='good') for i in range(20) for j in range(2)]
    rows.append(dict(split='test', patient_prefix='hidden', label='anomaly'))
    patients = ['P'+str(i) for i in range(20)]
    result = allocation(rows, patients, 10, 1)
    assert result == allocation(rows, patients, 10, 1)
    seed = int(hashlib.sha256(b'wsp-phase1|mfxr|k=10|r=1').hexdigest()[:16],16)
    assert seed_for(10, 1) == seed
    assert result['patient_ids'] == sorted(np.random.default_rng(seed).choice(sorted(patients), 10, replace=False).tolist())
    assert len(result['images']) == 20
    assert set(x['patient_id'] for x in result['images']) == set(result['patient_ids'])
    assert 'Phidden' not in result['patient_ids']


def test_hash_corpus_format(tmp_path, monkeypatch):
    import wsp_ml.data as data
    row = {'split': 'train', 'source_path': 'MFXR/train/good/1-1.jpg', 'raw_sha256': 'a'*64, 'normalized_sha256': 'b'*64, 'phash': 'c'*16}
    inv = tmp_path / 'inventory.json'
    inv.write_text(json.dumps({'archive_sha256': 'd'*64, 'records': [row]}))
    monkeypatch.setattr(data, 'PRIVATE', tmp_path / 'private')
    monkeypatch.setattr(data, 'inventory_paths', lambda: (inv, None))
    hash_corpus()
    result = json.loads((tmp_path / 'private/hash-corpus.json').read_text())
    assert set(result) == {'archive_sha256', 'raw_sha256', 'normalized_sha256', 'phash', 'basenames'}
    assert result['basenames'] == ['1-1.jpg']
    assert re.fullmatch('[0-9a-f]{16}', result['phash']['pool'][0])


def test_opaque_tokens_and_csv(tmp_path, monkeypatch):
    import csv
    import wsp_ml.data as data
    records = [dict(split='train', patient_prefix=str(i), anonymous_filename=f'{i}.png', label='good') for i in range(250)]
    inventory = tmp_path / 'inventory.json'
    inventory.write_text(json.dumps({'records': records}))
    monkeypatch.setattr(data, 'PRIVATE', tmp_path / 'private')
    monkeypatch.setattr(data, 'inventory_paths', lambda: (inventory, None))
    monkeypatch.setattr(data, 'validate_patient_map', lambda *args: None)
    data.private_dir(data.PRIVATE)
    (data.PRIVATE / 'patient-map-reviewed.json').write_text(json.dumps([{'patient_id': f'P{i}', 'split': 'train'} for i in range(250)]))
    data.sample()
    path = data.PRIVATE / 'allocations/k10/r1'
    allocation_data = json.loads((path / 'allocation.json').read_text())
    rows = list(csv.DictReader((path / 'labels.csv').open()))
    assert len(rows) == 10
    assert all(re.fullmatch('[0-9a-f]{12}', row['patient']) for row in rows)
    for row, item in zip(rows, allocation_data['images']):
        assert row['patient'] == hashlib.sha256(f"{allocation_data['seed']}|{item['patient_id']}".encode()).hexdigest()[:12]


@pytest.mark.parametrize('name', ['skelex', 'medsiglip', 'dinov3'])
def test_adapter_shapes_and_determinism(name):
    import torch
    from PIL import Image
    from wsp_ml.encoders import load_encoder, MODELS
    from wsp_ml.data import ROOT
    if not torch.cuda.is_available() or not (ROOT / 'models' / MODELS[name]).exists():
        pytest.skip('CUDA or local model unavailable')
    model = load_encoder(name, 'cuda', torch.float32)
    image = Image.new('RGB', (225, 180), (42, 42, 42))
    x = torch.stack([model.preprocess(image)] * 2).cuda()
    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
        a = model.forward(x)
        b = model.forward(x)
    assert torch.equal(a['pooled'], b['pooled'])
    assert a['pooled'].shape == (2, model.hidden_size)
    assert a['patch_tokens'][model.num_layers].shape[1] == (1024 if name == 'medsiglip' else 196)
    del model, a, b, x
    torch.cuda.empty_cache()
