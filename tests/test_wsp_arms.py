import json, os, stat
from pathlib import Path
import numpy as np
import pytest
from wsp_arms import core, arms_ac


def make_root(tmp_path, n_pool=240, d=16, seed=0, alloc_patients=(10, 'all')):
    """Synthetic root: pool of n_pool images (2 per patient), 1593 test files, allocations. No test manifest/labels exist."""
    rng = np.random.default_rng(seed)
    root = tmp_path / 'root'
    priv = root / 'data/locked/private'
    enc = 'skelex'
    names = [f'{i:04d}.png' for i in range(n_pool)]
    pat = [f'P{i // 2}' for i in range(n_pool)]
    lab = np.array([(i // 2) % 3 == 0 for i in range(n_pool)], dtype=int)  # patient-level label
    def feats(y):
        X = rng.normal(size=(len(y), d)).astype(np.float32)
        X[:, 0] += 2.5 * (2 * y - 1)
        return X
    pdir = root / 'features' / enc / 'pool'; pdir.mkdir(parents=True)
    np.save(pdir / 'pooled.npy', feats(lab)); (pdir / 'index.json').write_text(json.dumps({'filenames': names}))
    tnames = [f'{i:05d}t.png' for i in range(core.N_TEST)]
    tdir = priv / 'features' / enc / 'test'; tdir.mkdir(parents=True)
    np.save(tdir / 'pooled.npy', feats(rng.integers(0, 2, core.N_TEST))); (tdir / 'index.json').write_text(json.dumps({'filenames': tnames}))
    (priv / 'test-png').mkdir()
    for n in tnames: (priv / 'test-png' / n).write_bytes(b'x')
    def alloc(k, r, patients):
        imgs = [dict(anonymous_filename=names[i], label=int(lab[i]), patient_id=pat[i]) for i in range(n_pool) if pat[i] in patients]
        d_ = priv / 'allocations' / f'k{k}' / f'r{r}'; d_.mkdir(parents=True)
        (d_ / 'allocation.json').write_text(json.dumps({'seed': 123 + r, 'patient_ids': sorted(patients), 'images': imgs}))
    allp = sorted(set(pat))
    posp = sorted({pat[i] for i in range(n_pool) if lab[i]}); negp = sorted({pat[i] for i in range(n_pool) if not lab[i]})
    alloc('10', 1, set(rng.choice(posp, 5, replace=False).tolist()) | set(rng.choice(negp, 5, replace=False).tolist()))
    alloc('all', 1, set(allp))
    # single-class: only positive patients
    pos = sorted({pat[i] for i in range(n_pool) if lab[i]})[:5]
    alloc('20', 1, set(pos))
    # one positive patient only
    one = sorted({pat[i] for i in range(n_pool) if lab[i]})[:1] + sorted({pat[i] for i in range(n_pool) if not lab[i]})[:6]
    alloc('50', 1, set(one))
    return core.Paths(root), enc


def test_youden_midpoint_and_perfect():
    y = np.array([0, 0, 1, 1]); p = np.array([0.1, 0.3, 0.7, 0.9])
    t, j = core.youden_threshold(y, p)
    assert j == 1.0 and t == pytest.approx(0.5)
    # imperfect + tie: optimum region (0.3,0.7]
    y = np.array([0, 0, 1, 1, 1]); p = np.array([0.2, 0.6, 0.4, 0.8, 0.9])
    t, j = core.youden_threshold(y, p)
    assert j == pytest.approx(2 / 3) and t == pytest.approx(0.7)


def test_youden_single_class_fallback():
    assert core.threshold_from_oof(np.zeros(5), np.linspace(0, 1, 5))[:2] == (0.5, 'fixed_0.5_single_class')


def test_folds_grouped():
    pat = np.repeat([f'P{i}' for i in range(60)], 3); y = np.repeat(np.arange(60) % 2, 3)
    folds = core.make_folds(pat, y, 5)
    assert len(folds) == 5 and sum(map(len, folds)) == len(pat)
    seen = [set(pat[f]) for f in folds]
    assert all(not (seen[i] & seen[j]) for i in range(5) for j in range(i))
    pat2 = np.repeat([f'P{i}' for i in range(20)], 2)
    f2 = core.make_folds(pat2, np.repeat(np.arange(20) % 2, 2), 1)
    assert len(f2) == 20 and all(len(set(pat2[f])) == 1 for f in f2)


def test_k0_not_applicable(tmp_path):
    with pytest.raises(ValueError):
        core.parse_k('0')
    paths, enc = make_root(tmp_path)
    with pytest.raises(ValueError):
        arms_ac.run('A', enc, 0, 1, paths)


@pytest.mark.parametrize('arm', ['A', 'C'])
def test_run_normal(tmp_path, arm):
    paths, enc = make_root(tmp_path)
    rec = arms_ac.run(arm, enc, 10, 1, paths)
    d = paths.run_dir(arm, enc, '10', 1)
    lines = (d / 'predictions.csv').read_text().splitlines()
    assert lines[0] == 'image,prob' and len(lines) == core.N_TEST + 1
    probs = np.array([float(l.split(',')[1]) for l in lines[1:]])
    assert np.all((probs >= 0) & (probs <= 1))
    assert rec['cv']['scheme'] == 'LOPO' and rec['threshold_method'] == 'youden_oof_grouped'
    assert rec['oof_metrics']['auroc'] > 0.8  # separable synthetic data
    assert rec['C'] in core.C_GRID and rec['allocation_sha256'] and rec['code']['git_rev']
    assert stat.S_IMODE(os.stat(d / 'run.json').st_mode) == 0o600 and stat.S_IMODE(os.stat(d).st_mode) == 0o700
    # resumable: second call returns the stored record without recomputation
    mtime = (d / 'run.json').stat().st_mtime_ns
    arms_ac.run(arm, enc, 10, 1, paths)
    assert (d / 'run.json').stat().st_mtime_ns == mtime
    if arm == 'C':
        f = rec['self_training']['final']
        assert f['n_pseudo'] <= 0.5 * f['n_unlabeled'] and f['n_pseudo'] > 0


def test_a_probs_match_direct_fit(tmp_path):
    paths, enc = make_root(tmp_path)
    rec = arms_ac.run('A', enc, 'all', 1, paths)
    assert rec['cv']['scheme'] == '5-fold'
    pool = core.load_features(paths.pool_features(enc)); a = core.load_allocation(paths, 'all', 1)
    m = arms_ac.fit_lr(pool.X[pool.rows(a.images)], a.labels, rec['C'])
    test = core.load_test_features(paths, enc)
    got = np.array([float(l.split(',')[1]) for l in (paths.run_dir('A', enc, 'all', 1) / 'predictions.csv').read_text().splitlines()[1:]])
    assert np.allclose(got, m.predict_proba(test.X), atol=1e-8)


@pytest.mark.parametrize('arm', ['A', 'C'])
def test_single_class(tmp_path, arm):
    paths, enc = make_root(tmp_path)
    rec = arms_ac.run(arm, enc, 20, 1, paths)
    assert rec['single_class'] and rec['threshold'] == 0.5
    probs = {l.split(',')[1] for l in (paths.run_dir(arm, enc, '20', 1) / 'predictions.csv').read_text().splitlines()[1:]}
    assert probs == {'1'}


@pytest.mark.parametrize('arm', ['A', 'C'])
def test_one_positive_patient_default_C(tmp_path, arm):
    paths, enc = make_root(tmp_path)
    rec = arms_ac.run(arm, enc, 50, 1, paths)
    assert rec['C'] == 1.0 and 'default_C=1' in rec['C_selection']
    assert rec['threshold_method'] in ('youden_oof_grouped', 'fixed_0.5_single_class')


def test_self_train_cap_and_weights():
    rng = np.random.default_rng(0)
    Xl = rng.normal(size=(40, 4)); yl = np.arange(40) % 2; Xl[:, 0] += 3 * (2 * yl - 1)
    Xu = rng.normal(size=(100, 4))
    m, info = arms_ac.self_train(Xl, yl, Xu, 1.0)
    assert info['n_pseudo'] <= 50 and info['n_pseudo'] >= 40
    assert [r['total'] for r in info['rounds']] == sorted(r['total'] for r in info['rounds'])
    m2, info2 = arms_ac.self_train(Xl, yl, Xu[:0], 1.0)
    assert info2['skipped']


def test_predictions_validation(tmp_path):
    with pytest.raises(ValueError):
        core.write_predictions(tmp_path / 'p.csv', ['a'], [0.5])
    names = [str(i) for i in range(core.N_TEST)]
    with pytest.raises(ValueError):
        core.write_predictions(tmp_path / 'p.csv', names, [float('nan')] * core.N_TEST)


def test_no_test_label_access():
    src = ''.join(p.read_text() for p in Path(core.__file__).parent.glob('*.py'))
    assert 'test-manifest' not in src and 'test_manifest' not in src
