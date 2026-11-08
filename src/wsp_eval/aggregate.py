"""Aggregate private run outputs into disclosure-safe summaries."""
import csv
import json
from collections import defaultdict
from pathlib import Path
from .cli import load_run
from .metrics import bootstrap


def aggregate(args):
    groups = defaultdict(list)
    seen = set()
    with open(args.runs, newline='') as f:
        for row in csv.DictReader(f):
            key = (row['arm'], row['encoder'], row['k'])
            identity = (*key, row['r'])
            if identity in seen: raise ValueError(f'duplicate resample: {identity}')
            seen.add(identity)
            groups[key].append(load_run(row['path']))
    results = {key: bootstrap(runs, args.bootstrap, args.seed) for key, runs in groups.items()}
    tables = [{'arm': a, 'encoder': e, 'k': k, 'resamples': len(groups[(a,e,k)]), 'missing_predictions': sum(r[5] for r in groups[(a,e,k)]), 'evaluation_failure': any(r[5] for r in groups[(a,e,k)]), **{m: v['estimate'] for m,v in values.items()}} for (a,e,k),values in results.items()]
    baselines = [v['auroc']['estimate'] for (a,e,k),v in results.items() if a in ('B-full','B-lora') and k == 'all' and v['auroc']['estimate'] is not None]
    target = max(baselines)-0.02 if baselines else None
    requirement = {}
    for row in tables:
        key = row['arm'] + '/' + row['encoder']
        if target is not None and row['auroc'] is not None and row['auroc'] >= target:
            k = float('inf') if row['k'] == 'all' else int(row['k'])
            if key not in requirement or k < requirement[key]: requirement[key] = k
    requirement = {k: ('all' if v == float('inf') else v) for k,v in requirement.items()}
    contrasts = {}
    for (arm, enc, k), runs in groups.items():
        if arm == 'G' and ('F',enc,k) in groups:
            contrasts[enc+'/'+k] = bootstrap(runs, args.bootstrap, args.seed, groups[('F',enc,k)])
    # A conclusion based on a failed evaluation is not scientifically valid.
    failed = any(r['evaluation_failure'] for r in tables)
    encoders = ('skelex', 'medsiglip', 'dinov3')
    budgets = ('10', '20', '50', '100', '250', 'all')
    arms = ('A', 'B-full', 'B-lora', 'C', 'D-head', 'D-ft', 'E', 'H')
    expected = {(a, e, k, str(r)) for a in arms for e in encoders
                for k in (('0',) + budgets if a in ('D-head', 'D-ft', 'H') else budgets)
                for r in range(1, 2 if a == 'D-ft' else 6)}
    expected |= {(a, 'skelex', k, '1') for a in ('F', 'G') for k in ('10', '50')}
    complete = expected <= seen and not failed and all(row['auroc'] is not None for row in tables)
    gain = any(v['auroc']['estimate'] is not None and v['auroc']['estimate'] > 0
               and not any(r[5] for r in groups[('G', *key.split('/'))] + groups[('F', *key.split('/'))])
               for key, v in contrasts.items())
    fg_complete = all((a, 'skelex', k, '1') in seen for a in ('F', 'G') for k in ('10', '50'))
    gate = ('fail' if args.audit == 'fail' else 'pending evaluation failure' if failed else
            'pass' if gain and args.audit == 'pass' else 'pending audit' if gain else
            'fail' if fg_complete else 'pending results')
    g10 = [r['auroc'] for r in tables if r['arm'] == 'G' and r['k'] == '10' and r['auroc'] is not None]
    bfull = max(baselines) if baselines else None
    best_g10 = max(g10) if g10 else None
    to_count = lambda v: 993 if v == 'all' else v
    g_reqs = [to_count(v) for k,v in requirement.items() if k.startswith('G/')]
    rivals = [to_count(v) for k,v in requirement.items() if k.split('/')[0] in (*arms, 'F')]
    outcomes = {'level_1': None, 'level_2': None, 'level_3': None, 'level_4': None, 'level_5': None,
                'note': 'Conclusions require the complete planned matrix and investigator review.'}
    if complete:
        outcomes['level_1'] = best_g10 > bfull if best_g10 is not None and bfull is not None else None
        outcomes['level_2'] = best_g10 >= bfull-0.02 if best_g10 is not None and bfull is not None else None
        outcomes['level_3'] = min(g_reqs) <= min(rivals)/2 if g_reqs and rivals else None
        level4, level5 = [], []
        for row in tables:
            if row['arm'] != 'G': continue
            same = [r for r in tables if r['k'] == row['k'] and r['arm'] != 'G']
            level4.append(row['auroc'] > max(r['auroc'] for r in same))
            f = [r['auroc'] for r in same if r['arm'] == 'F' and r['encoder'] == row['encoder']]
            e = [r['auroc'] for r in same if r['arm'] == 'E']
            level5.append(row['auroc'] <= max(f) and row['auroc'] <= max(e))
        outcomes['level_4'] = any(level4)
        outcomes['level_5'] = all(level5)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    with (out/'table.csv').open('w', newline='') as f:
        if tables:
            writer = csv.DictWriter(f, fieldnames=list(tables[0])); writer.writeheader(); writer.writerows(tables)
    if tables:
        fields = list(tables[0]); lines = ['| ' + ' | '.join(fields) + ' |', '| ' + ' | '.join(['---']*len(fields)) + ' |']
        lines += ['| ' + ' | '.join(str(r[f]) for f in fields) + ' |' for r in tables]
        (out/'table.md').write_text('\n'.join(lines)+'\n')
    summary = {'matrix_complete': complete, 'evaluation_failure': failed, 'target': target, 'label_requirement': requirement, 'metrics': {'/'.join(k):v for k,v in results.items()}, 'G_minus_F': contrasts, 'gate': gate, 'audit': args.audit, 'outcome_levels': outcomes, 'other_fracture_controls': 'not estimable'}
    (out/'aggregate.json').write_text(json.dumps(summary, indent=2, allow_nan=False))
