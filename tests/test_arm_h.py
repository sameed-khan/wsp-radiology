import csv
import json

import numpy as np
import pytest

from wsp_arms import arm_h, core


def manifests(tmp_path):
    d = tmp_path / 'features/external-manifests'
    d.mkdir(parents=True)
    for name in arm_h.DATASETS:
        with (d / f'{name}.csv').open('w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['file', 'label'])
            w.writerows([[f'{name}/{i}.png', i % 2] for i in range(10)])
    return core.Paths(tmp_path)


def test_sample_is_seeded_without_replacement_and_counts(tmp_path):
    paths = manifests(tmp_path)
    a, counts, hashes = arm_h.external_sample(paths, 17)
    b, _, _ = arm_h.external_sample(paths, 17)
    assert a == b and len({p for p, _ in a}) == 17
    assert all(v == {'images': 10, 'negative': 5, 'positive': 5} for v in counts.values())
    assert len(hashes) == 3
    with pytest.raises(ValueError):
        arm_h.external_sample(paths, 31)


def test_manifest_rejects_escape(tmp_path):
    paths = manifests(tmp_path)
    with (tmp_path / 'features/external-manifests/MURA.csv').open('a') as f:
        f.write('../outside.png,1\n')
    with pytest.raises(ValueError, match='invalid manifest'):
        arm_h.external_sample(paths, 5)


def test_zero_shot_and_continuation_load_transfer(tmp_path, monkeypatch):
    import torch
    from safetensors.torch import save_file
    paths = manifests(tmp_path)
    out = arm_h.pretrain_dir(paths, 'skelex', 200)
    out.mkdir(parents=True)
    checkpoint = out / 'transfer.safetensors'
    save_file({'weight': torch.tensor([[3.0], [4.0]])}, str(checkpoint))
    (out / 'pretrain.json').write_text(json.dumps({'status': 'complete', 'sample_size': 200,
                                                   'checkpoint_sha256': core.sha256_file(checkpoint)}))
    test_dir = paths.test_png_dir()
    test_dir.mkdir(parents=True)
    for i in range(3):
        (test_dir / f'{i}.png').touch()
    monkeypatch.setattr(core, 'N_TEST', 3)
    monkeypatch.setattr(arm_h.arm_b, 'cap_vram', lambda: None)
    monkeypatch.setattr(torch.cuda, 'max_memory_allocated', lambda: 0)
    monkeypatch.setattr(torch.cuda, 'empty_cache', lambda: None)
    monkeypatch.setattr(arm_h.arm_b, 'build_model', lambda *a, **kw: (torch.nn.Linear(1, 2, bias=False), [], None))
    seen = []
    def predict(model, enc, files):
        seen.append(model.weight.detach().clone())
        return np.full(len(files), .6)
    monkeypatch.setattr(arm_h.arm_b, 'predict_files', predict)
    calls = []
    def train(model, groups, enc, files, labels, seed, **kw):
        calls.append(model.weight.detach().clone())
        return {'steps': 200, 'seconds': 1}
    monkeypatch.setattr(arm_h.arm_b, 'train_model', train)
    alloc = core.Allocation('10', 1, 12, ['a', 'b'], ['a.png', 'b.png'], ['a', 'b'], np.array([0, 1]), 'abc')
    monkeypatch.setattr(core, 'load_allocation', lambda *a: alloc)
    zero = arm_h.run('skelex', 0, 1, paths, sample_size=200)
    assert zero['threshold'] == .5 and not calls
    one = arm_h.run('skelex', 10, 1, paths, sample_size=200)
    assert one['steps'] == 200 and torch.equal(calls[0], torch.tensor([[3.], [4.]]))
    assert torch.equal(seen[0], seen[1])
    assert arm_h.run('skelex', 10, 1, paths, sample_size=200)['predictions_sha256'] == one['predictions_sha256']
    assert len(calls) == 1
    checkpoint.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='invalid transfer'):
        arm_h.run('skelex', 0, 2, paths, sample_size=200)
