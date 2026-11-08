import argparse
import csv
import json
import math
import os
from pathlib import Path

from .metrics import bootstrap
from .overlap import overlap

ROOT = Path('/home/skhanxx8/projects/wsp-radiology')
MANIFEST = ROOT / 'data/locked/private/test-manifest.json'


def private_dir(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT / 'data/locked/private').resolve()):
        raise ValueError('private output must be under data/locked/private')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


def save(path, value, private=False):
    path.write_text(json.dumps(value, indent=2, allow_nan=False))
    if private: path.chmod(0o600)


def load_run(path):
    obj = json.loads(Path(path).read_text())
    rows = obj['rows']
    return ([r['label'] for r in rows], [r['prob'] for r in rows], [r['patient_id'] for r in rows], obj['threshold'], [r['file'] for r in rows], sum(r.get('missing', False) for r in rows))


def score(args):
    out = private_dir(args.out)
    records = json.loads(Path(args.manifest).read_text())
    excluded = set(Path(args.exclude).read_text().splitlines()) if args.exclude else set()
    records = sorted((r for r in records if r['file'] not in excluded), key=lambda r:r['file'])
    if not records or len({r['file'] for r in records}) != len(records): raise ValueError('empty or duplicate manifest')
    preds = {}
    with open(args.preds, newline='') as f:
        for row in csv.DictReader(f):
            name = row['image']
            if name in preds: raise ValueError('duplicate prediction')
            try: value = float(row['prob'])
            except (ValueError, TypeError): value = float('nan')
            if math.isfinite(value) and not 0 <= value <= 1: raise ValueError('probability outside [0,1]')
            preds[name] = value
    if not 0 <= args.threshold <= 1: raise ValueError('threshold outside [0,1]')
    rows = []
    for r in records:
        p = preds.get(r['file'], float('nan'))
        missing = not math.isfinite(p)
        rows.append({'file': r['file'], 'patient_id': r['patient_id'], 'label': r['label'], 'prob': 0.5 if missing else p, 'missing': missing})
    result = {'run_id': args.run_id, 'threshold': args.threshold, 'rows': rows}
    save(out / 'private-results.json', result, True)
    run = load_run(out / 'private-results.json')
    summary = {'run_id': args.run_id, 'metrics': bootstrap([run], args.bootstrap, args.seed), 'images': len(rows), 'patients': len(set(run[2])), 'missing_predictions': sum(r['missing'] for r in rows), 'evaluation_failure': any(r['missing'] for r in rows), 'other_fracture_controls': 'not estimable'}
    save(out / 'summary.json', summary)


def main():
    p = argparse.ArgumentParser(prog='wsp-eval')
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('score')
    s.add_argument('--preds', required=True); s.add_argument('--threshold', type=float, required=True); s.add_argument('--run-id', required=True); s.add_argument('--out', required=True)
    s.add_argument('--manifest', default=str(MANIFEST)); s.add_argument('--exclude'); s.add_argument('--bootstrap', type=int, default=2000); s.add_argument('--seed', type=int, default=0)
    i = sub.add_parser('infer', help='run frozen F/G predictor and score it')
    i.add_argument('--workspace', required=True); i.add_argument('--images', required=True); i.add_argument('--image', required=True); i.add_argument('--run-id', required=True); i.add_argument('--out', required=True)
    i.add_argument('--manifest', default=str(MANIFEST)); i.add_argument('--exclude'); i.add_argument('--bootstrap', type=int, default=2000); i.add_argument('--seed', type=int, default=0)
    o = sub.add_parser('overlap'); o.add_argument('--external-root', action='append', required=True); o.add_argument('--test-manifest', default=str(MANIFEST)); o.add_argument('--out', required=True); o.add_argument('--workers', type=int, default=12)
    a = sub.add_parser('aggregate'); a.add_argument('--runs', required=True, help='CSV: arm,encoder,k,r,path to private-results.json'); a.add_argument('--out', required=True); a.add_argument('--bootstrap', type=int, default=2000); a.add_argument('--seed', type=int, default=0); a.add_argument('--audit', choices=['pass','fail','unknown'], default='unknown')
    args = p.parse_args()
    if args.command == 'score': score(args)
    elif args.command == 'infer':
        from .inference import infer
        infer(args)
    elif args.command == 'overlap': overlap(args.external_root, private_dir(args.out), args.test_manifest, args.workers)
    else:
        from .aggregate import aggregate
        aggregate(args)

if __name__ == '__main__': main()
