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
    from . import arms_ac
    t = time.monotonic()
    try:
        rec = arms_ac.run(arm, enc, k, r, force=force)
        return (arm, enc, k, r, 'ok', time.monotonic() - t, rec.get('threshold'))
    except Exception as e:  # reported, not swallowed silently
        return (arm, enc, k, r, f'FAILED: {type(e).__name__}: {e}', time.monotonic() - t, None)


def main(argv=None):
    os.umask(0o077)
    p = argparse.ArgumentParser(prog='wsp-arms')
    sub = p.add_subparsers(dest='cmd', required=True)
    g = sub.add_parser('grid', help='run (resumable) all encoders x k x r for an arm')
    g.add_argument('--arm', required=True, choices=('A', 'C'))
    g.add_argument('--encoders', nargs='*', default=None)
    g.add_argument('--ks', nargs='*', default=None)
    g.add_argument('--rs', nargs='*', type=int, default=None)
    g.add_argument('--jobs', type=int, default=8)
    g.add_argument('--force', action='store_true')
    args = p.parse_args(argv)
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
