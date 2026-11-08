from __future__ import annotations

import argparse
import json
import os
import sys
import time


def _set_threads(n):
    for v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[v] = str(n)


def _one(args):
    arm, enc, k, r, force = args
    t = time.monotonic()
    try:
        if arm == 'E':
            from . import arms_e as mod
        else:
            from . import arms_ac as mod
        rec = mod.run(arm, enc, k, r, force=force)
        return (arm, enc, k, r, 'ok', time.monotonic() - t, rec.get('threshold'))
    except Exception as e:  # reported, not swallowed silently
        return (arm, enc, k, r, f'FAILED: {type(e).__name__}: {e}', time.monotonic() - t, None)


def _grid_b(args):
    """Sequential (one GPU job at a time), resumable: completed runs (run.json status complete) are skipped."""
    from . import arm_b, core
    variants = [args.arm.split('-', 1)[1]] if '-' in args.arm else (args.variants or list(arm_b.VARIANTS))
    encs = args.encoders or list(core.ENCODERS)
    ks = [core.parse_k(k) for k in (args.ks or core.KS)]
    rs = args.rs or list(core.RS)
    paths = core.Paths.default()
    tasks = [(f'B-{v}', e, k, r) for v in variants for e in encs for k in ks for r in rs]
    start = time.monotonic()
    n_ok = n_skip = 0
    failed = []
    for arm, e, k, r in tasks:
        t = time.monotonic()
        if not args.force and core.is_complete(paths.run_dir(arm, e, k, r)):
            n_skip += 1
            continue
        try:
            arm_b.run(arm, e, k, r, paths=paths, force=args.force, steps=args.steps, micro_batch=args.micro_batch)
            n_ok += 1
            print(f'{arm} {e} k={k} r={r} ok {time.monotonic() - t:.1f}s', flush=True)
        except Exception as ex:
            failed.append((arm, e, k, r, f'{type(ex).__name__}: {ex}'))
            print(f'{arm} {e} k={k} r={r} FAILED {type(ex).__name__}: {ex}', file=sys.stderr, flush=True)
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
    print(json.dumps({'arm': args.arm, 'runs': len(tasks), 'ok': n_ok, 'skipped_complete': n_skip, 'failed': len(failed),
                      'wall_seconds': round(time.monotonic() - start, 1)}))
    return 1 if failed else 0


def _time_b(args):
    from . import arm_b, core
    paths = core.Paths.default()
    res = []
    for e in (args.encoders or list(core.ENCODERS)):
        for v in args.variants:
            t = arm_b.time_one(e, v, paths=paths, steps=args.steps, micro_batch=args.micro_batch)
            print(json.dumps(t), flush=True)
            res.append(t)
    est = arm_b.estimate_grid(res, paths=paths)
    print(json.dumps(est, indent=1))
    out = args.out or str(paths.private / 'runs/baselines/B-timing.json')
    core.write_private_atomic(out, json.dumps({'timings': res, 'estimate': est}, indent=1))
    return 0


def main(argv=None):
    os.umask(0o077)
    os.environ.setdefault('PYTORCH_ALLOC_CONF', 'expandable_segments:True')
    p = argparse.ArgumentParser(prog='wsp-arms')
    sub = p.add_subparsers(dest='cmd', required=True)
    g = sub.add_parser('grid', help='run (resumable) all encoders x k x r for an arm')
    g.add_argument('--arm', required=True, choices=('A', 'C', 'E', 'B', 'B-full', 'B-lora'))
    g.add_argument('--variants', nargs='*', default=None, choices=('full', 'lora'), help='arm B variants (default both)')
    g.add_argument('--steps', type=int, default=None, help='arm B: override step count (testing only; recorded)')
    g.add_argument('--micro-batch', type=int, default=None, help='arm B: micro-batch (grad accumulation to 16)')
    g.add_argument('--encoders', nargs='*', default=None)
    g.add_argument('--ks', nargs='*', default=None)
    g.add_argument('--rs', nargs='*', type=int, default=None)
    g.add_argument('--jobs', type=int, default=8)
    g.add_argument('--force', action='store_true')
    sp = sub.add_parser('sae', help='arm E: train the per-encoder top-k SAE on pool patch tokens (GPU, once per encoder)')
    sp.add_argument('--encoders', nargs='*', default=None)
    sp.add_argument('--steps', type=int, default=None)
    sp.add_argument('--force', action='store_true')
    tb = sub.add_parser('time-b', help='arm B: 50-step timing run per encoder/variant + full-grid GPU-hour estimate')
    tb.add_argument('--encoders', nargs='*', default=None)
    tb.add_argument('--variants', nargs='*', default=['full', 'lora'])
    tb.add_argument('--steps', type=int, default=50)
    tb.add_argument('--micro-batch', type=int, default=None)
    tb.add_argument('--out', default=None)
    args = p.parse_args(argv)
    if args.cmd == 'time-b':
        return _time_b(args)
    if args.cmd == 'grid' and args.arm.startswith('B'):
        return _grid_b(args)
    if args.cmd == 'sae':
        from . import core, sae_train
        for e in (args.encoders or list(core.ENCODERS)):
            sae_train.train_one(e, steps=args.steps, force=args.force)
        return 0
    jobs = max(1, min(args.jobs, 8))
    _set_threads(1)
    from . import core
    encs = args.encoders or list(core.ENCODERS)
    ks = [core.parse_k(k) for k in (args.ks or core.KS)]
    rs = args.rs or list(core.RS)
    tasks = [(args.arm, e, k, r, args.force) for e in encs for k in ks for r in rs]
    start = time.monotonic()
    results = []
    if jobs == 1:
        results = [_one(t) for t in tasks]
    else:
        import multiprocessing as mp
        with mp.get_context('spawn').Pool(jobs) as pool:
            for res in pool.imap_unordered(_one, tasks):
                results.append(res)
                print(f'{res[0]} {res[1]} k={res[2]} r={res[3]} {res[4]} {res[5]:.1f}s', flush=True)
    failed = [r for r in results if r[4] != 'ok']
    summary = {'arm': args.arm, 'runs': len(tasks), 'ok': len(tasks) - len(failed), 'failed': len(failed),
               'wall_seconds': round(time.monotonic() - start, 1), 'sum_run_seconds': round(sum(r[5] for r in results), 1)}
    print(json.dumps(summary))
    for f in failed:
        print(f, file=sys.stderr)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
