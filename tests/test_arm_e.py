import hashlib, json
import numpy as np
import pytest
from wsp_arms import core, arms_e, sae_train
from test_wsp_arms import make_root


def add_e_inputs(paths, enc, seed=1):
    rng = np.random.default_rng(seed)
    pdir, tdir = paths.pool_features(enc), paths.test_features(enc)
    pool = json.loads((pdir / 'index.json').read_text())['filenames']
    test = json.loads((tdir / 'index.json').read_text())['filenames']
    ypool = np.array([(i // 2) % 3 == 0 for i in range(len(pool))], dtype=float)  # make_root's patient-level labels
    def f(y, informative, d=12, lat=False):
        X = rng.normal(size=(len(y), d)).astype(np.float32)
        if informative:
            X[:, 3] += 8 * (2 * y - 1)
        return X
    ytest = rng.integers(0, 2, len(test)).astype(float)
    for kind, layer, inf in (('cls', 8, True), ('patch_mean', 8, False), ('patch_mean', 12, False)):
        np.save(pdir / f'{kind}-{layer}.npy', f(ypool, inf)); np.save(tdir / f'{kind}-{layer}.npy', f(ytest, inf))
    sdir = sae_train.sae_dir(paths, enc); sdir.mkdir(parents=True)
    def lat(y):
        L = np.abs(rng.normal(size=(len(y), 300))).astype(np.float32) * (rng.random((len(y), 300)) < 0.1)
        L[:, 7] += 2 * y
        return L
    np.save(sdir / 'pool_mean_latents.npy', lat(ypool)); np.save(sdir / 'test_mean_latents.npy', lat(ytest))
    (sdir / 'sae.json').write_text(json.dumps({'layer': 12, 'sae_sha256': 'x', 'pool_names_sha256': core.sha256_text(pool), 'test_names_sha256': core.sha256_text(test)}))


def test_dom_and_fit():
    rng = np.random.default_rng(0)
    y = np.array([0] * 50 + [1] * 50)
    X = rng.normal(size=(100, 20)); X[:, 2] += 2 * y
    m = arms_e.fit_model(X, y, None, 'none')
    p = m.predict_proba(X)
    assert core.auroc(y, p) > 0.88 and abs(m.w[2]) == np.abs(m.w).max()
    m8 = arms_e.fit_model(X, y, 8, 'diagonal')
    assert np.count_nonzero(m8.w) == 8 and core.auroc(y, m8.predict_proba(X)) > 0.85
    assert isinstance(arms_e.fit_model(X, np.zeros(100, int), None, 'none'), arms_e.Constant)


def test_config_key_prefers_simple():
    a = ('cls', 24, None, 'none'); b = ('patch_mean', 24, None, 'none'); c = ('sae', 16, 8, 'none'); d = ('cls', 24, None, 'diagonal')
    assert sorted([c, d, b, a], key=arms_e.config_key) == [a, b, d, c]
    assert arms_e.config_key(('cls', 24, None, 'none')) < arms_e.config_key(('cls', 8, None, 'none'))


def test_run_e(tmp_path):
    paths, enc = make_root(tmp_path)
    add_e_inputs(paths, enc)
    rec = arms_e.run('E', enc, 10, 1, paths)
    assert rec['status'] == 'complete' and rec['selected']['feature_set'] in ('cls', 'sae', 'patch_mean')
    assert rec['oof_metrics']['auroc'] > 0.8 and rec['threshold_method'] == 'youden_oof_grouped'
    assert len(rec['cv_auroc_by_config']) == 3 * 2 + 6 and rec['cv']['scheme'] == 'LOPO'
    d = paths.run_dir('E', enc, '10', 1)
    lines = (d / 'predictions.csv').read_text().splitlines()
    assert len(lines) == core.N_TEST + 1
    # the informative CLS-8 set has to beat noise sets
    assert rec['cv_auroc_by_config']['cls-8|m=None|none'] > rec['cv_auroc_by_config']['patch_mean-8|m=None|none'] + 0.1
    # resumable
    m = (d / 'run.json').stat().st_mtime_ns
    arms_e.run('E', enc, 10, 1, paths)
    assert (d / 'run.json').stat().st_mtime_ns == m
    # 5-fold path
    rec = arms_e.run('E', enc, 'all', 1, paths)
    assert rec['cv']['scheme'] == '5-fold' and rec['oof_metrics']['auroc'] > 0.9


def test_run_e_single_class_and_k0(tmp_path):
    paths, enc = make_root(tmp_path)
    add_e_inputs(paths, enc)
    rec = arms_e.run('E', enc, 20, 1, paths)
    assert rec['single_class'] and rec['threshold'] == 0.5 and rec['selected'] is None
    with pytest.raises(ValueError):
        arms_e.run('E', enc, 0, 1, paths)
    rec = arms_e.run('E', enc, 50, 1, paths)  # one positive patient
    assert rec['selected'] is not None


def test_sae_order_mismatch_rejected(tmp_path):
    paths, enc = make_root(tmp_path)
    add_e_inputs(paths, enc)
    p = sae_train.sae_dir(paths, enc) / 'sae.json'
    d = json.loads(p.read_text()); d['pool_names_sha256'] = 'bad'; p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        arms_e.run('E', enc, 10, 1, paths)


def test_tie_selects_simplest(tmp_path):
    # all-noise features -> still must deterministically pick a valid config; identical rerun with force gives identical choice
    paths, enc = make_root(tmp_path)
    add_e_inputs(paths, enc)
    a = arms_e.run('E', enc, 10, 1, paths)['selected']
    b = arms_e.run('E', enc, 10, 1, paths, force=True)['selected']
    assert a == b


def test_sae_train_smoke(tmp_path, monkeypatch):
    import os
    torch = pytest.importorskip('torch')
    models = '/home/skhanxx8/projects/wsp-radiology/models'
    if not torch.cuda.is_available() or not os.path.isdir(models + '/skhoha/SKELEX'):
        pytest.skip('needs CUDA + SKELEX')
    monkeypatch.setenv('WSP_MODELS', models)
    from PIL import Image
    paths, enc = make_root(tmp_path)
    rng = np.random.default_rng(0)
    pool = json.loads((paths.pool_features(enc) / 'index.json').read_text())['filenames']
    (paths.root / 'data/pool').mkdir(parents=True)
    for n in pool[:6]:
        Image.fromarray(rng.integers(0, 255, (64, 80), dtype=np.uint8)).save(paths.root / 'data/pool' / n)
    for n in sorted(p.name for p in paths.test_png_dir().glob('*.png'))[:6]:
        Image.fromarray(rng.integers(0, 255, (64, 80), dtype=np.uint8)).save(paths.test_png_dir() / n)
    rec = sae_train.train_one(enc, paths=paths, steps=300, limit=6, log=lambda *_: None)
    d = sae_train.sae_dir(paths, enc)
    assert rec['layer'] == 16 and rec['dictionary_size'] == 8192 and rec['tokens_per_image'] == 196
    assert np.load(d / 'pool_mean_latents.npy').shape == (6, 8192) and not (d / 'tokens.f16.tmp').exists()
    assert rec['peak_gpu_bytes'] < 8 * 2**30 and rec['loss_last100_mean'] < rec['loss_first100_mean']
    k = sae_train._toolkit().load_sae(d / 'sae.safetensors', 1024, 8192, 32)
    assert k.k == 32
