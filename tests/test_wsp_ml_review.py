import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from wsp_ml.external import external_manifest


def put(path, data='x'):
    path.parent.mkdir(parents=True, exist_ok=True)
    if data == 'x' and path.suffix.lower() in ('.png', '.jpg'):
        from PIL import Image
        Image.new('RGB', (4, 4)).save(path)
    else:
        path.write_text(data)


def test_external_manifests_and_invalid_entries(tmp_path):
    g = tmp_path / 'GRAZPEDWRI-DX'
    put(g / 'dataset.csv', 'filestem,fracture_visible\na,1\nb,\n')
    for n in ('a', 'b'): put(g / 'images' / f'{n}.png')
    f = tmp_path / 'FracAtlas/FracAtlas'
    put(f / 'dataset.csv', 'image_id,fractured\na.jpg,1\nb.jpg,0\n')
    for n in ('a', 'b'): put(f / 'images' / f'{n}.jpg')
    m = tmp_path / 'MURA/MURA-v1.1'
    put(m / 'train_labeled_studies.csv', 'MURA-v1.1/train/X/p/s/,1\n')
    put(m / 'valid_labeled_studies.csv', 'MURA-v1.1/valid/X/q/s/,0\n')
    for p in ('train/X/p/s/a.png', 'train/X/p/s/b.png', 'valid/X/q/s/c.png'): put(m / p)
    put(m / 'train/X/p/s/._a.png', 'sidecar')
    put(m / 'train/X/p/s/bad.png', 'junk')
    for name, labels in [('GRAZPEDWRI-DX', [1, 0]), ('FracAtlas', [1, 0]), ('MURA', [1, 1, 0])]:
        paths, entries, counts = external_manifest(tmp_path, name)
        assert [e['label'] for e in entries] == labels
        assert [e['file'] for e in entries] == [str(p.relative_to(tmp_path)) for p in paths]
        assert counts['images'] == len(entries)
        if name == 'MURA':
            assert counts['skipped_appledouble'] == counts['skipped_undecodable'] == 1
    put(f / 'images/duplicate/a.jpg', 'different')
    with pytest.raises(ValueError, match='conflicting'): external_manifest(tmp_path, 'FracAtlas')
    (f / 'images/duplicate/a.jpg').unlink()
    (f / 'images/b.jpg').unlink()
    with pytest.raises(ValueError, match='do not match'): external_manifest(tmp_path, 'FracAtlas')
    put(m / 'valid_labeled_studies.csv', 'MURA-v1.1/valid/X/q/s/,0\nMURA-v1.1/valid/X/q/s/,1\n')
    with pytest.raises(ValueError, match='duplicate'): external_manifest(tmp_path, 'MURA')


def setup_extract(tmp_path, monkeypatch):
    import wsp_ml.features as f
    import wsp_ml.encoders as enc
    monkeypatch.setattr(f.torch.cuda, 'is_available', lambda: True)
    monkeypatch.setattr(f.torch.cuda, 'max_memory_allocated', lambda: 0)
    monkeypatch.setattr(f, 'image_paths', lambda dataset: ([tmp_path / f'{i}.png' for i in range(12)], tmp_path / 'output'))
    monkeypatch.setattr(f.subprocess, 'check_output', lambda *a, **k: 'revision')
    monkeypatch.setenv('WSP_MODELS', str(tmp_path / 'alternate'))
    alt = tmp_path / 'alternate' / enc.MODELS['skelex']
    canonical = tmp_path / 'canonical' / enc.MODELS['skelex']
    put(alt / 'model.safetensors', 'alternate')
    put(canonical / 'model.safetensors', 'canonical')
    captured = []
    monkeypatch.setattr(f, 'load_encoder', lambda *a, **kw: captured.append(kw['path']) or SimpleNamespace(layer_indices_default=[1], num_layers=1))
    return f, alt, captured


def test_alternate_model_provenance_and_empty_hashes(tmp_path, monkeypatch):
    import hashlib
    f, alt, captured = setup_extract(tmp_path, monkeypatch)
    monkeypatch.setattr(f, 'run_batch', lambda adapter, paths: {'pooled': np.ones((len(paths), 2))})
    result = f.extract('skelex', 'pool', None)
    index = json.loads((Path(result['output']) / 'index.json').read_text())
    assert captured == [alt.resolve()]
    assert index['model_sha256'] == {'model.safetensors': hashlib.sha256(b'alternate').hexdigest()}
    (alt / 'model.safetensors').unlink()
    with pytest.raises(ValueError, match='weight files'): f.extract('skelex', 'pool', None)


@pytest.mark.parametrize('bad', [np.nan, np.inf, -np.inf])
@pytest.mark.parametrize('bad_call', [1, 2, 5])
def test_nonfinite_batches_never_publish_index(tmp_path, monkeypatch, bad, bad_call):
    f, _, _ = setup_extract(tmp_path, monkeypatch)
    calls = 0
    def batch(adapter, paths):
        nonlocal calls
        calls += 1
        return {'pooled': np.full((len(paths), 2), bad if calls == bad_call else 1.)}
    monkeypatch.setattr(f, 'run_batch', batch)
    with pytest.raises(ValueError, match='non-finite'): f.extract('skelex', 'pool', None)
    assert not (tmp_path / 'output/skelex/pool/index.json').exists()

@pytest.mark.parametrize('name,tolerance', [('skelex', 0.7), ('medsiglip', 0.009), ('dinov3', 0.08)])
def test_preprocess_against_hf_nonuniform(name, tolerance):
    from PIL import Image
    from transformers import AutoImageProcessor
    from wsp_ml.encoders import model_path, preprocess
    path = model_path(name)
    if not path.exists():
        pytest.skip('local model unavailable')
    y, x = np.indices((183, 231))
    image = Image.fromarray(((x * 3 + y * 2) % 256).astype(np.uint8))
    processor = AutoImageProcessor.from_pretrained(path, local_files_only=True)
    reference = processor(images=image.convert('RGB'), return_tensors='pt')['pixel_values'][0]
    actual = preprocess(image, name)
    assert actual.shape == reference.shape
    assert (actual - reference).abs().max().item() < tolerance


def test_write_manifests_columns(tmp_path):
    from wsp_ml.external import write_manifests
    g = tmp_path / 'GRAZPEDWRI-DX'
    put(g / 'dataset.csv', 'filestem,fracture_visible\na,1\nb,\n')
    for n in ('a', 'b'): put(g / 'images' / f'{n}.png')
    f = tmp_path / 'FracAtlas/FracAtlas'
    put(f / 'dataset.csv', 'image_id,fractured\na.jpg,1\nb.jpg,0\n')
    for n in ('a', 'b'): put(f / 'images' / f'{n}.jpg')
    m = tmp_path / 'MURA/MURA-v1.1'
    put(m / 'train_labeled_studies.csv', 'MURA-v1.1/train/X/p/s/,1\n')
    put(m / 'valid_labeled_studies.csv', 'MURA-v1.1/valid/X/q/s/,0\n')
    for p in ('train/X/p/s/a.png', 'valid/X/q/s/c.png'): put(m / p)
    summary = write_manifests(tmp_path, tmp_path / 'out')
    assert summary['MURA']['images'] == 2 and summary['MURA']['label_entries'] == 2
    lines = (tmp_path / 'out/GRAZPEDWRI-DX.csv').read_text().splitlines()
    assert lines == ['file,label', 'GRAZPEDWRI-DX/images/a.png,1', 'GRAZPEDWRI-DX/images/b.png,0']
