"""Aggregate private run outputs into disclosure-safe summaries."""
import csv
import json
from collections import defaultdict
from pathlib import Path
from .cli import load_run
from .metrics import bootstrap


def aggregate(args):
    groups = defaultdict(list)
    with open(args.runs, newline='') as f:
        for row in csv.DictReader(f):
            key = (row['arm'], row['encoder'], row['k'])
            groups[key].append(load_run(row['path']))
    results = {key: bootstrap(runs, args.bootstrap, args.seed) for key, runs in groups.items()}
    tables = [{'arm': a, 'encoder': e, 'k': k, 'resamples': len(groups[(a,e,k)]), **{m: v['estimate'] for m,v in values.items()}} for (a,e,k),values in results.items()]
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
    gain = any(v['auroc']['estimate'] is not None and v['auroc']['estimate'] > 0 for v in contrasts.values())
    gate = ('fail' if args.audit == 'fail' else 'pending results' if not contrasts else
            'fail' if not gain else 'pass' if args.audit == 'pass' else 'pending audit')
    g10 = [r['auroc'] for r in tables if r['arm'] == 'G' and r['k'].isdigit() and int(r['k']) <= 10 and r['auroc'] is not None]
    bfull = max(baselines) if baselines else None
    best_g10 = max(g10) if g10 else None
    g_reqs = [v for k,v in requirement.items() if k.startswith('G/') and v != 'all']
    rivals = [v for k,v in requirement.items() if k.split('/')[0] in ('A','B-full','B-lora','C','D-head','D-ft','E','F','H') and v != 'all']
    outcomes = {'level_1': best_g10 > bfull if best_g10 is not None and bfull is not None else None,
                'level_2': best_g10 >= bfull-0.02 if best_g10 is not None and bfull is not None else None,
                'level_3': min(g_reqs) <= min(rivals)/2 if g_reqs and rivals else None,
                'level_4': None, 'level_5': None,
                'note': 'Levels 3-5 require complete arm/budget results and investigator review; missing arms are not treated as failures.'}
    required = {'A','B-full','B-lora','C','D-head','D-ft','E','F','G','H'}
    if not required.issubset({r['arm'] for r in tables}): outcomes['level_3'] = None
    level4, level5 = [], []
    for row in tables:
        if row['arm'] != 'G' or row['auroc'] is None: continue
        same = [r for r in tables if r['k'] == row['k'] and r['arm'] != 'G' and r['auroc'] is not None]
        if required - {'G'} <= {r['arm'] for r in same}:
            level4.append(row['auroc'] > max(r['auroc'] for r in same))
        f = [r['auroc'] for r in same if r['arm'] == 'F' and r['encoder'] == row['encoder']]
        e = [r['auroc'] for r in same if r['arm'] == 'E']
        if f and e: level5.append(row['auroc'] <= max(f) and row['auroc'] <= max(e))
    if level4: outcomes['level_4'] = any(level4)
    if level5 and len(level5) == sum(r['arm'] == 'G' for r in tables): outcomes['level_5'] = all(level5)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    with (out/'table.csv').open('w', newline='') as f:
        if tables:
            writer = csv.DictWriter(f, fieldnames=list(tables[0])); writer.writeheader(); writer.writerows(tables)
    if tables:
        fields = list(tables[0]); lines = ['| ' + ' | '.join(fields) + ' |', '| ' + ' | '.join(['---']*len(fields)) + ' |']
        lines += ['| ' + ' | '.join(str(r[f]) for f in fields) + ' |' for r in tables]
        (out/'table.md').write_text('\n'.join(lines)+'\n')
    summary = {'target': target, 'label_requirement': requirement, 'metrics': {'/'.join(k):v for k,v in results.items()}, 'G_minus_F': contrasts, 'gate': gate, 'audit': args.audit, 'outcome_levels': outcomes, 'other_fracture_controls': 'not estimable'}
    (out/'aggregate.json').write_text(json.dumps(summary, indent=2, allow_nan=False))
