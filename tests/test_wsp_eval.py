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


def test_docker_inference_arguments(tmp_path):
    from wsp_eval.inference import docker_args
    for name in ('workspace', 'images', 'out', 'models'): (tmp_path/name).mkdir()
    cmd = docker_args('agent:local', 'wsp-eval-test', tmp_path/'workspace', tmp_path/'images', tmp_path/'out', tmp_path/'models')
    assert cmd[:6] == ['docker', 'create', '--name', 'wsp-eval-test', '--network', 'none']
    assert '--gpus' in cmd and 'device=0' in cmd
    assert f'type=bind,src={tmp_path}/models,dst=/inputs/models,readonly' in cmd
    assert f'type=bind,src={tmp_path}/workspace,dst=/workspace,readonly' in cmd
    assert f'type=bind,src={tmp_path}/images,dst=/eval/images,readonly' in cmd
    assert f'type=bind,src={tmp_path}/out,dst=/eval/out' in cmd
    assert cmd[-5:] == ['/workspace/output/model/predict.py', '--images', '/eval/images', '--out', '/eval/out/preds.csv']


def test_overlap_exif_normalization_and_cache(tmp_path, monkeypatch):
    import imagehash
    import wsp_eval.overlap as module
    from wsp_prep.core import load_image_bytes
    monkeypatch.setattr(module, 'CACHE', tmp_path/'cache')
    root = tmp_path/'images'; root.mkdir()
    im = Image.new('RGB', (30, 20), 'white')
    for x in range(10):
        for y in range(5): im.putpixel((x, y), (0, 0, 0))
    exif = Image.Exif(); exif[274] = 6
    path = root/'oriented.jpg'; im.save(path, exif=exif)
    h = str(imagehash.phash(load_image_bytes(path.read_bytes())))
    assert module._hash(path)[1] == h
    manifest = tmp_path/'manifest'; manifest.write_text(json.dumps([{'file':'test', 'phash':h}]))
    report = overlap([root], tmp_path/'out', manifest, 1)
    assert report['pair_counts_by_distance']['0'] == 1
    assert report['audit_complete']


def test_bootstrap_rejects_different_ordered_images():
    import pytest
    a = ([0,1], [.1,.9], ['a','b'], .5, ['a1','b1'], 0)
    b = ([0,1], [.1,.9], ['a','b'], .5, ['a2','b2'], 0)
    with pytest.raises(ValueError, match='identical ordered images'):
        bootstrap([a], 2, 0, [b])
    with pytest.raises(ValueError, match='identical ordered images'):
        bootstrap([a,b], 2, 0)


def _aggregate_fixture(tmp_path, rows):
    import csv
    from argparse import Namespace
    from wsp_eval.aggregate import aggregate
    path = tmp_path/'runs.csv'
    with path.open('w', newline='') as f:
        writer = csv.writer(f); writer.writerow(['arm','encoder','k','r','path']); writer.writerows(rows)
    aggregate(Namespace(runs=path, out=tmp_path/'out', bootstrap=2, seed=1, audit='pass'))
    return json.loads((tmp_path/'out/aggregate.json').read_text())


def _run_file(tmp_path, name, probs, missing=False):
    p = tmp_path/name
    p.write_text(json.dumps({'threshold':.5, 'rows':[{'file':str(i), 'patient_id':str(i), 'label':i, 'prob':v, 'missing':missing and i == 1} for i,v in enumerate(probs)]}))
    return p


def test_partial_matrix_gate_and_outcomes_pending(tmp_path):
    p = _run_file(tmp_path, 'run', [.1,.9])
    rows = [(arm,'skelex','10','1',p) for arm in ('A','B-full','B-lora','C','D-head','D-ft','E','F','G','H')]
    result = _aggregate_fixture(tmp_path, rows)
    assert result['gate'] == 'pending results'
    assert all(result['outcome_levels'][f'level_{n}'] is None for n in (3,4,5))


def test_failed_evaluation_blocks_gate(tmp_path):
    f = _run_file(tmp_path, 'f', [.9,.5], True)
    g = _run_file(tmp_path, 'g', [.1,.9])
    result = _aggregate_fixture(tmp_path, [('F','skelex','10','1',f),('G','skelex','10','1',g)])
    assert result['evaluation_failure'] and result['gate'] != 'pass'
    assert result['G_minus_F']['skelex/10']['auroc']['estimate'] > 0


def test_duplicate_resample_rejected(tmp_path):
    import pytest
    p = _run_file(tmp_path, 'run', [.1,.9]); row = ('F','skelex','10','1',p)
    with pytest.raises(ValueError, match='duplicate resample'): _aggregate_fixture(tmp_path, [row,row])


def test_all_requirement_is_993_patients(tmp_path):
    p = _run_file(tmp_path, 'high', [.1,.9]); low = _run_file(tmp_path, 'low', [.9,.1])
    encoders = ('skelex','medsiglip','dinov3')
    arms = ('A','B-full','B-lora','C','D-head','D-ft','E','H')
    rows = [(a,e,k,str(r),p if k == 'all' else low) for a in arms for e in encoders
            for k in (('0','10','20','50','100','250','all') if a in ('D-head','D-ft','H') else ('10','20','50','100','250','all'))
            for r in range(1, 2 if a == 'D-ft' else 6)]
    rows += [(a,'skelex',k,'1',p if a == 'G' else low) for a in ('F','G') for k in ('10','50')]
    result = _aggregate_fixture(tmp_path, rows)
    assert result['matrix_complete']
    assert result['label_requirement']['A/skelex'] == 'all'
    assert result['outcome_levels']['level_3'] is True


def test_inference_timeout_and_gpu_violation_stop_container(tmp_path, monkeypatch):
    from argparse import Namespace
    import subprocess
    import pytest
    import wsp_eval.inference as inference
    import wsp_eval.cli as cli
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    monkeypatch.setattr(inference.os, 'chown', lambda *args: None)
    workspace = tmp_path/'workspace'; (workspace/'output/model').mkdir(parents=True)
    (workspace/'output/model/threshold.json').write_text('{"threshold": 0.3}')
    images = tmp_path/'images'; images.mkdir()
    stopped = []
    cid = 'a'*64
    def check_output(command, **kwargs):
        if command[1] == 'create': return cid
        if command[1] == 'inspect': return 'true 0'
        raise AssertionError(command)
    def run(command, **kwargs):
        stopped.append(command)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(inference.subprocess, 'check_output', check_output)
    monkeypatch.setattr(inference.subprocess, 'run', run)
    def args(name):
        return Namespace(out=tmp_path/'data/locked/private/runs'/name, workspace=workspace, images=images, models=images, image='agent')
    monkeypatch.setattr(inference, '_gpu_usage', lambda _: 11265)
    with pytest.raises(RuntimeError, match='GPU memory cap'): inference.infer(args('gpu'))
    assert ['docker','rm','-f',cid] in stopped
    stopped.clear()
    times = iter([0, 10800])
    monkeypatch.setattr(inference.time, 'monotonic', lambda: next(times))
    with pytest.raises(TimeoutError): inference.infer(args('timeout'))
    assert ['docker','rm','-f',cid] in stopped


def test_inference_scores_with_frozen_threshold(tmp_path, monkeypatch):
    from argparse import Namespace
    import subprocess
    import wsp_eval.inference as inference
    import wsp_eval.cli as cli
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    monkeypatch.setattr(inference.os, 'chown', lambda *args: None)
    workspace = tmp_path/'workspace'; (workspace/'output/model').mkdir(parents=True)
    (workspace/'output/model/threshold.json').write_text('{"threshold": 0.37}')
    images = tmp_path/'images'; images.mkdir()
    cid = 'b'*64
    out = tmp_path/'data/locked/private/runs/run'
    def check_output(command, **kwargs):
        if command[1] == 'create': return cid
        return 'false 0'
    def run(command, **kwargs):
        if command[1] == 'start': (out/'inference-output/preds.csv').write_text('image,prob\n')
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(inference.subprocess, 'check_output', check_output)
    monkeypatch.setattr(inference.subprocess, 'run', run)
    monkeypatch.setattr(inference, '_gpu_usage', lambda _: 0)
    observed = []
    monkeypatch.setattr(cli, 'score', lambda args: observed.append(args.threshold))
    inference.infer(Namespace(out=out, workspace=workspace, images=images, models=images, image='agent'))
    assert observed == [.37]
