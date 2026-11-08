"""Real offline Docker acceptance; synthetic images and labels only."""
import json
import os
from argparse import Namespace

import pytest
from PIL import Image

pytestmark = pytest.mark.skipif(os.environ.get('WSP_LIVE') != '1', reason='requires Docker and GPU')


def test_frozen_inference_end_to_end(tmp_path, monkeypatch):
    import wsp_eval.cli as cli
    from wsp_eval.inference import infer
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    workspace = tmp_path / 'snapshot/workspace'
    model = workspace / 'output/model'; model.mkdir(parents=True)
    images = tmp_path / 'images'; images.mkdir()
    models = tmp_path / 'models'; models.mkdir()
    (models / 'marker').write_text('model')
    manifest = []
    for i in range(20):
        name = f'{i:02d}.png'
        Image.new('RGB', (8, 8), (i, i, i)).save(images / name)
        manifest.append({'file': name, 'patient_id': str(i), 'label': i % 2})
    manifest_path = tmp_path / 'manifest.json'; manifest_path.write_text(json.dumps(manifest))
    (model / 'threshold.json').write_text('{"threshold": 0.37}')
    (model / 'predict.py').write_text('''import argparse, csv, pathlib, socket
p = argparse.ArgumentParser(); p.add_argument('--images'); p.add_argument('--out'); a = p.parse_args()
try:
    socket.create_connection(('1.1.1.1', 443), timeout=2)
except OSError:
    pass
else:
    raise RuntimeError('network unexpectedly reachable')
assert pathlib.Path('/inputs/models/marker').read_text() == 'model'
for path in ['/workspace/forbidden', '/eval/images/forbidden', '/inputs/models/forbidden']:
    try: pathlib.Path(path).write_text('bad')
    except OSError: pass
    else: raise RuntimeError('read-only mount writable')
with open(a.out, 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['image', 'prob'])
    for path in sorted(pathlib.Path(a.images).glob('*.png')): w.writerow([path.name, 0.5])
''')
    out = tmp_path / 'data/locked/private/runs/synthetic'
    args = Namespace(out=out, workspace=workspace, images=images, models=models,
                     image='wsp-agent:toolkit-step1', manifest=manifest_path,
                     exclude=None, bootstrap=10, seed=1, run_id='synthetic')
    infer(args)
    summary = json.loads((out / 'summary.json').read_text())
    result = json.loads((out / 'private-results.json').read_text())
    assert summary['images'] == 20 and not summary['evaluation_failure']
    assert result['threshold'] == 0.37 and all(r['prob'] == 0.5 for r in result['rows'])
    assert (out / 'inference-output/preds.csv').stat().st_mode & 0o777 == 0o600
    (model / 'threshold.json').unlink()
    args.out = out.parent / 'missing-threshold'
    with pytest.raises(FileNotFoundError, match='threshold.json'):
        infer(args)
