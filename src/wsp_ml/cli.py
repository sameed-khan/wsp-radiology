from __future__ import annotations
import argparse
import json
import os
import time
from . import data


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(prog='wsp-ml')
    subs = parser.add_subparsers(dest='command', required=True)
    for name in ('patient-map', 'sample', 'test-images', 'hash-corpus', 'cuda-smoke', 'external-manifests', 'audit-features'):
        subs.add_parser(name)
    features = subs.add_parser('features')
    features.add_argument('--encoder', required=True, choices=('skelex', 'medsiglip', 'dinov3'))
    features.add_argument('--set', required=True, dest='dataset')
    features.add_argument('--limit', type=int)
    args = parser.parse_args()
    start = time.monotonic()
    if args.command == 'features':
        from .features import extract
        result = extract(args.encoder, args.dataset, args.limit)
    elif args.command == 'cuda-smoke':
        from .features import cuda_smoke
        result = cuda_smoke()
    elif args.command == 'audit-features':
        from .features import audit_features
        result = audit_features()
    elif args.command == 'external-manifests':
        from .external import write_manifests
        result = write_manifests()
    else:
        result = getattr(data, args.command.replace('-', '_'))()
    receipt = {'command': args.command, 'seconds': round(time.monotonic()-start, 3), 'result': result}
    runtime = data.ROOT / '.runtime'
    runtime.mkdir(exist_ok=True, mode=0o700)
    name = args.command if args.command != 'features' else f'features-{args.encoder}-{args.dataset.replace(":", "-")}'
    path = runtime / f'l1-{name}.json'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(receipt, f, indent=2)
    os.chmod(path, 0o600)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
