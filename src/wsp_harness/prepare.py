"""Prepare private F/G inputs and a point-in-time, non-authorizing readiness receipt."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import difflib
import json
import os
from pathlib import Path
import subprocess
import uuid

from .config import digest, load_inputs, render
from .evidence import sha256
from .run import REPO, utc
from .sae import validate_package

DATA_ROOT = Path('/home/skhanxx8/projects/wsp-radiology')
EXPECTED_POOL = 2993


def _command(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        return p.stdout.strip() if p.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def prepare(root: Path, k: int, resample: int, image: str, proxy_image: str, data_root: Path = DATA_ROOT):
    if k not in (10, 50) or resample != 1:
        raise ValueError('F/G preparation supports only k=10 or 50 and resample=1')
    root, data_root = root.resolve(), data_root.resolve()
    private = data_root / 'data/locked/private'
    source = private / f'allocations/k{k}/r{resample}'
    # Agents get the sanitized copy (random copy order, constant timestamps); see scripts/sanitize_agent_pool.py.
    pool = (data_root / 'data/agent-pool/current').resolve()
    n_pool = sum(p.is_file() for p in pool.iterdir())
    inputs = {arm: load_inputs(root, arm) for arm in ('F', 'G')}
    now = datetime.now(timezone.utc)
    values = {'k': k, 'n_pool': n_pool, 'start_utc': utc(now),
              'deadline_utc': utc(now + timedelta(hours=24)), 'now_utc': utc(now), 'remaining': '1 day, 0:00:00'}
    prompts = {arm: render(i.launch_template, {**values, 'arm': arm, 'weight_sentence': i.weight_sentence})
               for arm, i in inputs.items()}
    normalized = {arm: render(i.launch_template, {**values, 'arm': '<ARM>', 'weight_sentence': '<WEIGHT>'})
                  for arm, i in inputs.items()}
    # Each invocation creates an immutable-in-practice, agent-only labels directory.
    base = data_root / '.runtime/run-inputs'
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    dest = base / f'k{k}-r{resample}-{uuid.uuid4().hex}'
    dest.mkdir(mode=0o700)
    labels = dest / 'labels'
    labels.mkdir(mode=0o700)
    content = (source / 'labels.csv').read_bytes()
    fd = os.open(labels / 'labels.csv', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(content)
    checks = {}
    def check(name, ok, **details):
        checks[name] = {'ok': bool(ok), **details}
    status = _command(['git', '-C', str(REPO), 'status', '--porcelain', '--untracked-files=normal'])
    rev = _command(['git', '-C', str(REPO), 'rev-parse', 'HEAD'])
    check('git_clean', status == '' and bool(rev), revision=rev)
    check('n_pool', n_pool == EXPECTED_POOL, actual=n_pool, expected=EXPECTED_POOL, path=str(pool))
    mtimes = {p.stat().st_mtime_ns for p in pool.iterdir() if p.is_file()}
    check('pool_sanitized', 'locked' not in pool.parts and len(mtimes) == 1, path=str(pool), distinct_mtimes=len(mtimes))
    check('prompt_diff', normalized['F'] == normalized['G'])
    sae_path = data_root / 'data/agent-sae/current'
    try:
        sae_hash = validate_package(sae_path)
        sae_error = None
    except ValueError as exc:
        sae_hash, sae_error = None, str(exc)
    check('sae_package', sae_hash is not None, path=str(sae_path), manifest_sha256=sae_hash, error=sae_error)
    check('labels', sha256(labels / 'labels.csv') == digest(content), sha256=digest(content), path=str(labels))
    for name, path in [('allocation', source / 'allocation.json'), ('corpus', private / 'hash-corpus.json')]:
        try:
            value = sha256(path)
        except OSError:
            value = None
        check(name, value is not None, sha256=value, path=str(path))
    for name, tag in [('agent_image', image), ('proxy_image', proxy_image)]:
        raw = _command(['docker', 'image', 'inspect', tag, '--format', '{{json .}}'])
        try:
            obj = json.loads(raw or 'null') or {}
        except ValueError:
            obj = {}
        check(name, bool(obj.get('Id')), tag=tag, image_id=obj.get('Id'), repo_digests=obj.get('RepoDigests') or [])
    ca = Path('/etc/ssl/certs/ca-certificates.crt')
    check('ca', ca.is_file() and os.access(ca, os.R_OK), path=str(ca))
    free = _command(['nvidia-smi', '--id=0', '--query-gpu=memory.free', '--format=csv,noheader,nounits'])
    try:
        free_mib = int(free or '')
    except ValueError:
        free_mib = None
    check('gpu_free', free_mib is not None and free_mib >= 22 * 1024, free_mib=free_mib, required_mib=22 * 1024)
    running = _command(['docker', 'ps', '--filter', 'name=wsp-agent-', '--format', '{{.Names}}'])
    check('no_running_agents', running == '', containers=running.splitlines() if running is not None else None)
    auth = _command(['pi', 'auth', 'check', '--provider', 'anthropic', '--json', '--no-refresh'])
    try:
        auth_status = json.loads(auth or '{}').get('status')
    except ValueError:
        auth_status = None
    check('anthropic_auth', auth_status == 'ready', status=auth_status)
    for name, path in [('models', data_root / 'models'), ('external', data_root / 'data/external/extracted')]:
        check(name, path.is_dir(), path=str(path))
    report = {'created_utc': utc(now), 'k': k, 'resample': resample, 'checks': checks,
              'input_hashes': {arm: i.hashes for arm, i in inputs.items()},
              'prompt_sha256': {arm: digest(p.encode()) for arm, p in prompts.items()},
              'note': 'Point-in-time checks only; orchestrator must approve launch, freeze revision/images, verify all prerequisites and recheck resources. Preview times are not launch times.'}
    report['ready'] = all(c['ok'] for c in checks.values())
    report_path = dest / 'readiness.json'
    fd = os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    return report_path, report, prompts


def cmd_prepare(args):
    path, report, prompts = prepare(Path(args.root or os.environ.get('WSP_ROOT') or REPO), args.k, args.resample,
                                    args.image, args.proxy_image)
    for arm in ('F', 'G'):
        print(f'--- ARM {arm} PROMPT (preview) ---\n{prompts[arm]}')
    print('--- F/G PROMPT DIFF ---')
    print(''.join(difflib.unified_diff(prompts['F'].splitlines(keepends=True), prompts['G'].splitlines(keepends=True),
                                     fromfile='F', tofile='G')))
    print(json.dumps({'readiness_file': str(path), **report}, indent=2))
    return 0 if report['ready'] else 1
