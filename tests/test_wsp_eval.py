import numpy as np
from wsp_eval.metrics import auc, bootstrap, metrics
from wsp_eval.overlap import overlap
from PIL import Image
import json


def test_auc_ties_against_sklearn():
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(12)
    for _ in range(20):
        y = rng.integers(0, 2, 100)
        p = rng.integers(0, 10, 100) / 10
        assert abs(auc(y, p) - roc_auc_score(y, p)) < 1e-12


def test_bootstrap_paired_identical_runs():
    run = ([0, 0, 1, 1], [.1, .2, .7, .9], ['a', 'a', 'b', 'c'], .5)
    result = bootstrap([run], 50, 3, [run])
    assert result['auroc']['estimate'] == 0
    assert result['auroc']['ci'] == [0, 0]
    assert metrics(*run)['auroc'] == 1


def test_overlap_identical_image(tmp_path, monkeypatch):
    import wsp_eval.overlap as module
    monkeypatch.setattr(module, 'CACHE', tmp_path/'cache')
    root = tmp_path/'images'; root.mkdir()
    Image.new('RGB', (20,20), 'white').save(root/'a.png')
    import imagehash
    with Image.open(root/'a.png') as im: h = str(imagehash.phash(im.convert('RGB')))
    manifest = tmp_path/'manifest.json'; manifest.write_text(json.dumps([{'file':'private.png','phash':h}]))
    report = overlap([root], tmp_path/'out', manifest, workers=1)
    assert report['pair_counts_by_distance']['0'] == 1


def test_score_missing_predictions(tmp_path, monkeypatch):
    from argparse import Namespace
    import wsp_eval.cli as cli
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    private = tmp_path/'data/locked/private'; private.mkdir(parents=True)
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps([{'file':'a.png','patient_id':'p1','label':0},{'file':'b.png','patient_id':'p2','label':1}]))
    preds = tmp_path/'preds.csv'; preds.write_text('image,prob\na.png,0.2\n')
    cli.score(Namespace(out=private/'run', manifest=manifest, exclude=None, preds=preds, threshold=.5, run_id='synthetic', bootstrap=10, seed=1))
    summary = json.loads((private/'run/summary.json').read_text())
    assert summary['missing_predictions'] == 1
    assert summary['evaluation_failure']
    assert 'a.png' not in json.dumps(summary)
