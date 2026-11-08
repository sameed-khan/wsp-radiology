import hashlib
import json
import numpy as np
import pytest
from wsp_arms import arm_d, core, arm_d_labels
from test_wsp_arms import make_root


def setup_cache(tmp_path):
    paths, enc = make_root(tmp_path, n_pool=60, d=4)
    pool = paths.root / 'data/pool'; pool.mkdir(parents=True)
    prompt = paths.root / 'config/arm-d-prompt.md'; prompt.parent.mkdir(); prompt.write_text('prompt')
    ph = hashlib.sha256(prompt.read_bytes()).hexdigest()
    cache = paths.private / 'arm-d/labels.jsonl'; cache.parent.mkdir()
    rows = []
    for i in range(60):
        name = f'{i:04d}.png'; (pool / name).write_bytes(name.encode())
        rows.append(dict(image=name, image_sha256=core.sha256_file(pool / name), prompt_sha256=ph,
                         model=arm_d_labels.MODEL, p_monteggia=(i * 7) % 101))
    cache.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return paths, enc, cache, rows


def test_coverage_validation(tmp_path):
    paths, _, cache, rows = setup_cache(tmp_path)
    cache.write_text(''.join(json.dumps(r)+'\n' for r in rows[:-1]))
    with pytest.raises(ValueError, match='processed 59/60'):
        arm_d.load_cache(paths)
    assert arm_d.load_cache(paths, True)[1]['missing'] == 1
    rows[-1]['p_monteggia'] = None
    cache.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    assert arm_d.load_cache(paths)[1]['failed_excluded'] == 1
    cache.write_text(cache.read_text() + json.dumps(rows[0])+'\n')
    with pytest.raises(ValueError, match='duplicate'):
        arm_d.load_cache(paths)


def test_head_grid_cells_and_resume(tmp_path):
    paths, enc, cache, rows = setup_cache(tmp_path)
    zero = arm_d.run('D-head', enc, 0, 1, paths)
    assert zero['C'] == 1 and zero['threshold'] == .5 and zero['n_true_images'] == 0
    rec = arm_d.run('D-head', enc, 10, 1, paths)
    assert rec['threshold_method'] == 'youden_oof_grouped' and rec['sample_weights']['true'] == 5
    assert rec['oof_metrics']['n'] == rec['n_true_images']
    out = paths.run_dir('D-head', enc, '10', 1)
    assert len((out / 'predictions.csv').read_text().splitlines()) == core.N_TEST + 1
    stamp = (out / 'run.json').stat().st_mtime_ns
    arm_d.run('D-head', enc, 10, 1, paths)
    assert stamp == (out / 'run.json').stat().st_mtime_ns
    assert arm_d.run('D-head', enc, 20, 1, paths)['constant_prior'] == 1
    cache.write_text(''.join(json.dumps(r)+'\n' for r in rows[:-1]))
    arm_d.run('D-head', enc, 0, 1, paths, allow_partial=True)
    assert core.is_complete(paths.run_dir('D-head-partial', enc, '0', 1))


def test_cli_synthetic_and_resumption(tmp_path, monkeypatch, capsys):
    from wsp_arms.cli import main
    paths, enc, _, _ = setup_cache(tmp_path)
    monkeypatch.setenv('WSP_ROOT', str(paths.root))
    args = ['grid', '--arm', 'D-head', '--encoders', enc, '--ks', '0', '--rs', '1', '--jobs', '1']
    assert main(args) == 0
    out = paths.run_dir('D-head', enc, '0', 1) / 'run.json'
    stamp = out.stat().st_mtime_ns
    assert main(args) == 0 and out.stat().st_mtime_ns == stamp
    assert main(['grid', '--arm', 'D-ft', '--rs', '2']) == 1
    assert 'restricted to r=1' in capsys.readouterr().err


def test_ft_hard_labels_and_override(tmp_path, monkeypatch):
    paths, enc, _, rows = setup_cache(tmp_path)
    import torch
    monkeypatch.setattr(arm_d.arm_b, 'cap_vram', lambda: None)
    monkeypatch.setattr(arm_d.arm_b, 'build_model', lambda *a, **k: (object(), [], object()))
    seen = {}
    def train(model, groups, enc, files, labels, seed, **kwargs):
        seen.update(zip([p.name for p in files], labels.tolist()))
        return {'steps': 1, 'losses': [1.]}
    monkeypatch.setattr(arm_d.arm_b, 'train_model', train)
    monkeypatch.setattr(arm_d.arm_b, 'predict_files', lambda model, enc, files: np.full(len(files), .4))
    monkeypatch.setattr(torch.cuda, 'max_memory_allocated', lambda: 0)
    monkeypatch.setattr(torch.cuda, 'empty_cache', lambda: None)
    rec = arm_d.run('D-ft', enc, 10, 1, paths, steps=1)
    alloc = core.load_allocation(paths, 10, 1)
    assert all(seen[n] == y for n, y in zip(alloc.images, alloc.labels))
    assert all(seen[r['image']] == (r['p_monteggia'] >= 50) for r in rows if r['image'] not in alloc.images)
    assert rec['threshold'] == .5
    arm_d.run('D-ft', enc, 0, 1, paths, steps=1)
    assert all(seen[r['image']] == (r['p_monteggia'] >= 50) for r in rows)
    with pytest.raises(ValueError, match='r=1'):
        arm_d.run('D-ft', enc, 0, 2, paths)
