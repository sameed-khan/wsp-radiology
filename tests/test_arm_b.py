import json, os, sys
import numpy as np
import pytest
from PIL import Image
from wsp_arms import core, arm_b, cli
from test_wsp_arms import make_root


def test_steps_seed_weights():
    assert arm_b.n_steps(25) == 200 and arm_b.n_steps(723) == 200 and arm_b.n_steps(2993) == 749
    assert arm_b.n_steps(801) == 201
    assert arm_b.train_seed('10', 3) == 3010 and arm_b.train_seed('all', 2) == 2993
    w = arm_b.class_weights([0, 0, 0, 1])
    assert w[0] == pytest.approx(4 / 6) and w[1] == pytest.approx(2.0)


def test_layer_id_decay_mapping():
    L = 24
    assert arm_b.layer_id('embeddings.patch_embeddings.weight', L) == 0
    assert arm_b.layer_id('encoder.layer.0.attention.attention.query.weight', L) == 1
    assert arm_b.layer_id('encoder.layer.23.output.dense.weight', L) == 24
    assert arm_b.layer_id('vision_model.encoder.layers.5.mlp.fc1.weight', 27) == 6
    assert arm_b.layer_id('layer.3.mlp.up_proj.weight', L) == 4
    assert arm_b.layer_id('layernorm.weight', L) == L + 1 and arm_b.layer_id('vision_model.head.probe', 27) == 28
    assert arm_b.layer_id('embeddings.cls_token', L) == 0


def test_augment_deterministic_and_bounded():
    im = Image.fromarray((np.random.default_rng(0).random((120, 100)) * 255).astype(np.uint8))
    a = arm_b.augment(im, np.random.default_rng(5), 'skelex'); b = arm_b.augment(im, np.random.default_rng(5), 'skelex')
    assert np.array_equal(np.asarray(a), np.asarray(b)) and a.mode == 'RGB'
    assert a.size[0] <= 100 and a.size[1] <= 120
    sizes = {arm_b.augment(im, np.random.default_rng(i), 'dinov3').size for i in range(20)}
    assert len(sizes) > 5
    for s in sizes:  # area >= ~0.7 of original (rounding tolerance), aspect ratio in range
        assert 0.65 * 12000 <= s[0] * s[1] <= 12000 and 0.75 <= s[0] / s[1] * (120 / 100) / (120 / 100) <= 1.3


def test_trainset_order_covers_epochs():
    ts = arm_b.TrainSet('skelex', ['a'] * 5, [0, 1, 0, 1, 1], 3, 15)
    assert len(ts) == 15 and all(sorted(ts.order[i:i + 5]) == [0, 1, 2, 3, 4] for i in (0, 5, 10))
    assert ts.order == arm_b.TrainSet('skelex', ['a'] * 5, [0, 1, 0, 1, 1], 3, 15).order


def test_single_class_and_resume(tmp_path, monkeypatch):
    paths, enc = make_root(tmp_path)
    rec = arm_b.run('B-lora', enc, '20', 1, paths=paths)  # single-class allocation: no training, no GPU
    assert rec['single_class'] and rec['threshold'] == 0.5 and rec['n_predictions'] == core.N_TEST
    d = paths.run_dir('B-lora', enc, '20', 1)
    assert (d / 'run.json').stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):
        arm_b.run('B-lora', enc, '0', 1, paths=paths)
    with pytest.raises(ValueError):
        arm_b.run('B-foo', enc, '20', 1, paths=paths)


def test_grid_skips_completed(tmp_path, monkeypatch, capsys):
    paths, enc = make_root(tmp_path)
    monkeypatch.setenv('WSP_ROOT', str(paths.root))
    calls = []
    real = arm_b.run
    monkeypatch.setattr(arm_b, 'run', lambda arm, e, k, r, **kw: calls.append((arm, e, k, r)) or real(arm, e, k, r, **kw))
    argv = ['grid', '--arm', 'B-lora', '--encoders', enc, '--ks', '20', '--rs', '1']
    assert cli.main(argv) == 0 and len(calls) == 1
    assert cli.main(argv) == 0 and len(calls) == 1      # second pass skipped
    out = capsys.readouterr().out
    assert '"skipped_complete": 1' in out
    assert cli.main(argv + ['--force']) == 0 and len(calls) == 2


def _real_png_root(tmp_path):
    paths, enc = make_root(tmp_path)
    rng = np.random.default_rng(1)
    pool = json.loads((paths.pool_features(enc) / 'index.json').read_text())['filenames']
    (paths.root / 'data/pool').mkdir(parents=True)
    for n in pool:
        Image.fromarray((rng.random((80, 64)) * 255).astype(np.uint8)).save(paths.root / 'data/pool' / n)
    for p in paths.test_png_dir().glob('*.png'):
        Image.fromarray((rng.random((48, 48)) * 255).astype(np.uint8)).save(p)
    return paths, enc


@pytest.mark.parametrize('variant', ['lora', 'full'])
def test_gpu_smoke_real_skelex(tmp_path, variant, monkeypatch):
    torch = pytest.importorskip('torch')
    models = os.environ.get('WSP_MODELS', '/home/skhanxx8/projects/wsp-radiology/models')
    if not torch.cuda.is_available() or not os.path.isdir(models + '/skhoha/SKELEX'):
        pytest.skip('needs CUDA + SKELEX')
    monkeypatch.setenv('WSP_MODELS', models)
    paths, enc = _real_png_root(tmp_path)
    rec = arm_b.run(f'B-{variant}', enc, '10', 1, paths=paths, steps=4, micro_batch=8)
    assert rec['status'] == 'complete' and rec['steps'] == 4 and rec['train_loss']['all_finite']
    assert rec['peak_vram_gb'] < 11 and rec['training_seed'] == 1010 and rec['threshold'] == 0.5
    g = {x['name']: x for x in rec['param_groups']}
    assert g['head']['lr'] == 1e-3
    if variant == 'lora':
        assert g['lora']['lr'] == 2e-4 and rec['n_trainable_params'] < 1e7
    else:  # layer-wise decay: last block lr = 1e-5*0.75^1, embeddings = 1e-5*0.75^25
        assert g['layer24']['lr'] == pytest.approx(1e-5 * 0.75) and g['layer0']['lr'] == pytest.approx(1e-5 * 0.75 ** 25)
    p = np.array([float(l.split(',')[1]) for l in (paths.run_dir(f'B-{variant}', enc, '10', 1) / 'predictions.csv').read_text().split('\n')[1:-1]])
    assert len(p) == core.N_TEST and np.all((p >= 0) & (p <= 1))
    # same seed -> same predictions (determinism of the data path / init)
    rec2 = arm_b.run(f'B-{variant}', enc, '10', 1, paths=paths, steps=4, micro_batch=8, force=True)
    p2 = np.array([float(l.split(',')[1]) for l in (paths.run_dir(f'B-{variant}', enc, '10', 1) / 'predictions.csv').read_text().split('\n')[1:-1]])
    assert np.abs(p - p2).max() < 0.05
