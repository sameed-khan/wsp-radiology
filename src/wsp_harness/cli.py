"""``wsp-harness``: launch, status, intervene, stop, verify, account and seal runs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

from .evidence import sha256, verify_events
from .run import HOST_ENV, REPO, create_run, utc

SUBAGENT_MODEL = 'claude-haiku-5-5'


# ---------------------------------------------------------------- helpers
def _root(args) -> Path:
    return Path(args.root or os.environ.get('WSP_ROOT') or REPO).resolve()


def _run_dir(args) -> Path:
    root = _root(args)
    ref = args.run
    cand = Path(ref)
    run = cand.resolve() if cand.is_dir() and (cand / 'launch.json').exists() else root / 'runs' / ref
    if not (run / 'launch.json').is_file():
        raise SystemExit(f'error: no such run: {ref}')
    return run


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _pid_alive(pid) -> bool:
    try:
        pid = int(pid)
        os.kill(pid, 0)
    except (TypeError, ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True
    try:  # a zombie is not alive
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z'
    except OSError:
        return False


def _append_intervention(run: Path, **fields) -> dict:
    record = {'utc': utc(datetime.now(timezone.utc)), **fields}
    with (run / 'interventions.jsonl').open('a') as f:
        f.write(json.dumps(record) + '\n')
    return record


def _status(run: Path) -> dict:
    status = _read_json(run / 'state/status.json') or {'run_id': run.name, 'phase': 'unknown'}
    pid = status.get('pid')
    if pid is None and (run / 'state/supervisor.pid').exists():
        pid = (run / 'state/supervisor.pid').read_text().strip()
    status['supervisor_alive'] = _pid_alive(pid)
    if not status['supervisor_alive'] and not str(status.get('phase', '')).startswith('frozen'):
        status['phase_note'] = 'supervisor process is not running and the run is not frozen'
    return status


# ---------------------------------------------------------------- commands
def cmd_launch(args) -> int:
    root = _root(args)
    if args.backend == 'infra':
        missing = [n for n in ('models_dir', 'external_dir', 'image', 'hash_corpus') if not getattr(args, n)]
        if missing:
            raise SystemExit('error: --backend infra needs ' + ', '.join('--' + m.replace('_', '-') for m in missing))
    run = create_run(root, args.arm, args.k, Path(args.labels), Path(args.pool), args.hours,
                     test_model=args.test_model, image=args.image if args.backend == 'infra' else 'ubuntu:24.04')
    if args.backend == 'infra':
        (run / 'state/backend.json').write_text(json.dumps({
            'models_dir': str(Path(args.models_dir).resolve()), 'external_dir': str(Path(args.external_dir).resolve()),
            'image': args.image, 'hash_corpus': str(Path(args.hash_corpus).resolve()),
            'gpu_mem_cap_gib': args.gpu_mem_cap_gib}, indent=2) + '\n')
    sup = [sys.executable, '-m', 'wsp_harness.supervisor', '--run', str(run), '--backend', args.backend,
           '--continue-after', str(args.continue_after), '--snapshot-interval', str(args.snapshot_interval),
           '--status-interval', str(args.status_interval)]
    out = run / 'recorder/supervisor.stdout'
    if args.daemonizer == 'systemd':
        cmd = ['systemd-run', '--user', '--collect', '--quiet', f'--unit=wsp-run-{run.name}',
               f'--working-directory={REPO}']
        cmd += [f'--setenv={k}={os.environ[k]}' for k in HOST_ENV if k in os.environ]
        cmd += ['--property=StandardOutput=append:' + str(out), '--property=StandardError=append:' + str(out)]
        subprocess.run(cmd + sup, check=True)
    else:
        # New session, no controlling terminal, no stdin: survives the parent and its terminal.
        with out.open('ab') as log:
            subprocess.Popen(sup, stdin=subprocess.DEVNULL, stdout=log, stderr=log, cwd=REPO,
                             start_new_session=True, close_fds=True)
    deadline = time.time() + 60
    while time.time() < deadline:
        st = _read_json(run / 'state/status.json')
        if st and st.get('container'):
            break
        if (run / 'state/supervisor.pid').exists() and not _alive_supervisor(run):
            print('warning: supervisor exited early (see recorder/supervisor.stdout)', file=sys.stderr)
            break
        time.sleep(0.5)
    else:
        print(f'warning: supervisor did not report status within 60 s (see {out})', file=sys.stderr)
    print(run.name)
    return 0


def _alive_supervisor(run: Path) -> bool:
    try:
        return _pid_alive((run / 'state/supervisor.pid').read_text().strip())
    except OSError:
        return False


def cmd_status(args) -> int:
    root = _root(args)
    if args.run:
        print(json.dumps(_status(_run_dir(args)), indent=2))
        return 0
    rows = []
    for run in sorted((root / 'runs').glob('*/launch.json')) if (root / 'runs').is_dir() else []:
        st = _status(run.parent)
        rows.append({k: st.get(k) for k in ('run_id', 'phase', 'reason', 'supervisor_alive', 'deadline_utc',
                                           'turns', 'tool_calls', 'continuations', 'retries', 'snapshots')})
    print(json.dumps(rows, indent=2))
    return 0


def cmd_intervene(args) -> int:
    run = _run_dir(args)
    if not args.note.strip():
        raise SystemExit('error: --note must not be empty')
    record = {'kind': args.kind, 'event': 'requested', 'note': args.note, 'by': 'orchestrator'}
    if args.kind == 'message':
        st = _status(run)
        if str(st.get('phase', '')).startswith('frozen') or not st['supervisor_alive']:
            raise SystemExit('error: run is not active; message not queued')
        folder = run / 'control/messages'
        folder.mkdir(exist_ok=True)
        name = f'{time.time_ns()}-{uuid.uuid4().hex[:8]}.json'
        tmp = folder / f'.{name}.tmp'
        tmp.write_text(json.dumps({'message': args.note, 'utc': utc(datetime.now(timezone.utc))}))
        record['file'] = name
        _append_intervention(run, **record)
        os.replace(tmp, folder / name)  # publish after logging
    else:
        _append_intervention(run, **record)
    print(json.dumps(record))
    return 0


def cmd_stop(args) -> int:
    run = _run_dir(args)
    if not args.reason.strip():
        raise SystemExit('error: --reason must not be empty')
    _append_intervention(run, kind='stop', event='requested', note=args.reason, by='orchestrator')
    tmp = run / 'control/.STOP_REQUEST.tmp'
    tmp.write_text(json.dumps({'reason': args.reason, 'utc': utc(datetime.now(timezone.utc)), 'by': 'orchestrator'}))
    os.replace(tmp, run / 'control/STOP_REQUEST.json')
    print(f'stop requested for {run.name}')
    return 0


# ---- session discovery
def _subagent_streams(run: Path) -> dict[str, dict]:
    folder = run / 'recorder/subagents'
    found: dict[str, dict] = {}
    for p in sorted(folder.glob('*.events.jsonl')):
        found.setdefault(p.name[:-len('.events.jsonl')], {})['events'] = p
    for p in sorted(folder.glob('*.jsonl')):
        if p.name.endswith('.events.jsonl'):
            continue
        m = re.search(r'_?([0-9a-f-]{36})\.jsonl$', p.name) or re.search(r'_([^_]+)\.jsonl$', p.name)
        sid = m.group(1) if m else p.stem
        found.setdefault(sid, {}).setdefault('sessions', []).append(p)
    return found


def _parent_sessions(run: Path) -> list[Path]:
    return sorted((run / 'recorder/sessions').glob('*.jsonl'))


def verify_run(run: Path) -> dict:
    problems: list[str] = []
    report: dict = {'run_id': run.name}
    events = run / 'recorder/rpc-events.jsonl'
    sessions = _parent_sessions(run)
    try:
        if not events.exists():
            raise ValueError('rpc-events.jsonl missing')
        parent = verify_events(events, sessions)
        if not parent['complete']:
            problems.append('parent events and session tool results differ')
    except ValueError as exc:
        parent = {'complete': False, 'error': str(exc)}
        problems.append(f'parent: {exc}')
    report['parent'] = parent
    times = run / 'recorder/rpc-receive-times.jsonl'
    if events.exists():
        n_events = sum(1 for _ in events.open('rb'))
        n_times = sum(1 for _ in times.open('rb')) if times.exists() else -1
        report['rpc_lines'], report['rpc_receive_time_lines'] = n_events, n_times
        if n_events != n_times:
            problems.append('rpc-events.jsonl and rpc-receive-times.jsonl line counts differ')
    subs, violations = {}, []
    for sid, parts in _subagent_streams(run).items():
        try:
            if 'events' not in parts or not parts.get('sessions'):
                raise ValueError('child has ' + ('no session file' if 'events' in parts else 'no events stream'))
            subs[sid] = verify_events(parts['events'], parts['sessions'])
            if not subs[sid]['complete']:
                problems.append(f'subagent {sid}: events and session results differ')
        except ValueError as exc:
            subs[sid] = {'complete': False, 'error': str(exc)}
            problems.append(f'subagent {sid}: {exc}')
        for session in parts.get('sessions', []):
            for entry in _jsonl(session):
                msg = entry.get('message') or {}
                if entry.get('type') == 'message' and msg.get('role') == 'assistant' and msg.get('model') != SUBAGENT_MODEL:
                    violations.append({'subagent': sid, 'model': msg.get('model')})
    report['subagents'] = subs
    report['subagent_model_violations'] = violations
    if violations:
        problems.append(f'{len(violations)} subagent assistant messages used a non-Haiku model')
    report['problems'] = problems
    report['complete'] = not problems and bool(sessions)
    if not sessions:
        report['problems'].append('no parent session file')
    return report


def _jsonl(path: Path):
    try:
        with path.open(encoding='utf-8') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    yield rec
    except OSError:
        return


def cmd_verify(args) -> int:
    report = verify_run(_run_dir(args))
    print(json.dumps(report, indent=2))
    return 0 if report['complete'] else 1


# ---- accounting
TOKEN_TYPES = ('input', 'output', 'cacheRead', 'cacheWrite', 'cacheWrite1h', 'reasoning')


def _new_bucket():
    return {'messages': 0, 'tokens': {t: 0 for t in TOKEN_TYPES}, 'totalTokens': 0,
            'cost': {t: 0.0 for t in ('input', 'output', 'cacheRead', 'cacheWrite', 'total')}, '_all_provider': True}


def _add(bucket: dict, usage: dict) -> None:
    bucket['messages'] += 1
    for t in TOKEN_TYPES:
        bucket['tokens'][t] += usage.get(t) or 0
    bucket['totalTokens'] += usage.get('totalTokens') or 0
    cost = usage.get('cost') or {}
    for t in bucket['cost']:
        bucket['cost'][t] += cost.get(t) or 0
    bucket['_all_provider'] &= cost.get('totalFromProvider') is True


def _finish(bucket: dict) -> dict:
    bucket['totalFromProvider'] = bucket.pop('_all_provider')
    bucket['cost'] = {k: round(v, 6) for k, v in bucket['cost'].items()}
    bucket['tokens'] = {k: v for k, v in bucket['tokens'].items() if v or k in ('input', 'output', 'cacheRead', 'cacheWrite')}
    return bucket


def _price_table(models: set[str]) -> dict:
    table: dict = {'source': 'pi --list-models + pi-ai provider catalog (USD per million tokens)', 'models': {}}
    try:
        table['pi_list_models'] = subprocess.run(['pi', '--list-models'], capture_output=True, text=True,
                                                 timeout=60).stdout.splitlines()
    except (OSError, subprocess.SubprocessError) as exc:
        table['pi_list_models_error'] = str(exc)
    try:
        cli = Path(shutil.which('pi') or '').resolve()
        data_dir = next(p for p in cli.parents if (p / 'node_modules/@earendil-works/pi-ai/dist/providers/data').is_dir()) \
            / 'node_modules/@earendil-works/pi-ai/dist/providers/data'
        for key in sorted(models):
            provider, _, model = key.partition('/')
            file = data_dir / f'{provider}.json'
            if not file.exists():
                continue
            for group in json.loads(file.read_text()).values():
                for entry in (group.values() if isinstance(group, dict) else group):
                    if isinstance(entry, dict) and entry.get('id') == model and 'cost' in entry:
                        table['models'][key] = entry['cost']
    except (StopIteration, OSError, ValueError) as exc:
        table['catalog_error'] = f'{type(exc).__name__}: {exc}'
    return table


def _gpu(run: Path) -> dict | None:
    files = sorted((run / 'state/gpu').glob('*.jsonl')) if (run / 'state/gpu').is_dir() else []
    if not files:
        return None
    samples, violations, kill_failed = [], 0, 0
    for f in files:
        for rec in _jsonl(f):
            if rec.get('event') == 'sample':
                try:
                    samples.append((datetime.fromisoformat(rec['time']).timestamp(), rec.get('memory_mib') or 0,
                                    rec.get('sm_utilization_percent')))
                except (KeyError, ValueError):
                    pass
            elif rec.get('event') == 'violation':
                violations += 1
            elif rec.get('event') == 'kill-failed':
                kill_failed += 1
    samples.sort()
    resident = busy = 0.0
    for (t0, mem, util), (t1, *_r) in zip(samples, samples[1:]):
        dt = min(t1 - t0, 600)
        if mem > 0:
            resident += dt
        if util:
            busy += dt * util / 100
    return {'samples': len(samples), 'peak_memory_mib': max((s[1] for s in samples), default=0),
            'gpu_memory_resident_hours': round(resident / 3600, 4),
            'gpu_busy_hours_estimate': round(busy / 3600, 4), 'cap_violations': violations,
            'kill_failed': kill_failed, 'note': 'sampled estimate; each interval capped at 600 s'}


def account_run(run: Path) -> dict:
    by_model: dict[str, dict] = {}
    by_source: dict[str, dict] = {}
    total = _new_bucket()
    errors = {'assistant_error_messages': 0, 'assistant_aborted_messages': 0}
    sources = [('parent', p) for p in _parent_sessions(run)]
    for sid, parts in _subagent_streams(run).items():
        sources += [(f'subagent:{sid}', p) for p in parts.get('sessions', [])]
    for source, path in sources:
        for entry in _jsonl(path):
            msg = entry.get('message') if entry.get('type') == 'message' else None
            if msg and msg.get('role') == 'assistant':
                usage, provider = msg.get('usage'), msg.get('provider')
                model = msg.get('responseModel') or msg.get('model')
                errors['assistant_error_messages'] += msg.get('stopReason') == 'error'
                errors['assistant_aborted_messages'] += msg.get('stopReason') == 'aborted'
            elif isinstance(entry.get('usage'), dict):  # usage / summary entries
                usage, provider, model = entry['usage'], entry.get('provider'), entry.get('model')
            else:
                continue
            if not isinstance(usage, dict):
                continue
            key = f'{provider}/{model}'
            for bucket in (by_model.setdefault(key, _new_bucket()), by_source.setdefault(source, _new_bucket()), total):
                _add(bucket, usage)
    interventions = list(_jsonl(run / 'interventions.jsonl'))
    count = lambda ev: sum(1 for i in interventions if i.get('event') == ev)
    status = _read_json(run / 'state/status.json') or {}
    launch = _read_json(run / 'launch.json', {})
    start = datetime.fromisoformat(launch['start_utc'].replace('Z', '+00:00'))
    frozen = str(status.get('phase', '')).startswith('frozen')
    end = datetime.fromisoformat(status['updated_utc'].replace('Z', '+00:00')) if frozen and status.get('updated_utc') \
        else datetime.now(timezone.utc)
    rpc_retry_events = 0
    for ev in _jsonl(run / 'recorder/rpc-events.jsonl'):
        rpc_retry_events += ev.get('type') == 'auto_retry_start'
    return {
        'run_id': run.name,
        'note': 'API-equivalent list-price estimates computed by Pi; totalFromProvider=false means not provider-billed '
                '(subscription OAuth access)',
        'by_model': {k: _finish(v) for k, v in sorted(by_model.items())},
        'by_source': {k: _finish(v) for k, v in sorted(by_source.items())},
        'total': _finish(total),
        'errors_and_retries': {**errors, 'auto_retry': count('auto-retry'), 'auto_retry_scheduled': count('auto-retry-scheduled'),
                               'pi_internal_auto_retry_events': rpc_retry_events,
                               'restarts': status.get('restarts'), 'continuations': status.get('continuations'),
                               'last_error': status.get('last_error')},
        'interventions': {'infra': sum(1 for i in interventions if i.get('kind') == 'infra'),
                          'message': sum(1 for i in interventions if i.get('kind') == 'message' and i.get('event') == 'requested'),
                          'stop': sum(1 for i in interventions if i.get('kind') == 'stop')},
        'wall_clock': {'start_utc': launch['start_utc'], 'end_utc': utc(end), 'ended': frozen,
                       'seconds': round((end - start).total_seconds(), 1)},
        'snapshots': status.get('snapshots'),
        'gpu': _gpu(run),
        'price_table': _price_table(set(by_model)),
    }


def cmd_account(args) -> int:
    report = account_run(_run_dir(args))
    if args.no_prices:
        report.pop('price_table', None)
    print(json.dumps(report, indent=2))
    return 0


# ---- seal
SECRET_PATTERNS = {
    'anthropic-key': re.compile(r'sk-ant-[A-Za-z0-9_\-]{20,}'),
    'openai-style-key': re.compile(r'\bsk-[A-Za-z0-9]{32,}'),
    'aws-access-key': re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    'github-token': re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}'),
    'huggingface-token': re.compile(r'\bhf_[A-Za-z0-9]{30,}'),
    'private-key': re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    'bearer-token': re.compile(r'(?i)\bbearer\s+[A-Za-z0-9._\-]{24,}'),
    'api-key-assignment': re.compile(r'(?i)["\']?(?:api[_-]?key|exaApiKey|access[_-]?token|refresh[_-]?token|secret)["\']?\s*[:=]\s*["\'][A-Za-z0-9._\-]{16,}["\']'),
}
EVIDENCE_TOP = ('recorder', 'state', 'control', 'interventions.jsonl', 'launch.json')


def _known_secrets() -> list[str]:
    values: list[str] = []
    for path in (Path.home() / '.pi/agent/auth.json', Path.home() / '.pi/exa-search.json'):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                stack += item.values()
            elif isinstance(item, list):
                stack += item
            elif isinstance(item, str) and len(item) >= 20 and ' ' not in item:
                values.append(item)
    return values


def _files(base: Path, run: Path):
    if base.is_file():
        yield base
    elif base.is_dir():
        for p in sorted(base.rglob('*')):
            if p.is_file() or p.is_symlink():
                yield p


def seal_run(run: Path, artifacts: Path, force: bool = False) -> dict:
    status = _read_json(run / 'state/status.json') or {}
    if not str(status.get('phase', '')).startswith('frozen') and not force:
        raise SystemExit(f'error: run phase is {status.get("phase")!r}, not frozen (use --force to override)')
    if _alive_supervisor(run) and not force:
        raise SystemExit('error: supervisor still running')
    dest = artifacts / 'runs' / run.name
    if dest.exists():
        raise SystemExit(f'error: {dest} already exists; refusing to overwrite sealed evidence')
    final = status.get('final_snapshot')
    tops = list(EVIDENCE_TOP)
    manifest_rel = f'snapshots/{final}/manifest.json' if final else None
    members: list[Path] = []
    for top in tops:
        members += [p for p in _files(run / top, run)]
    if manifest_rel and (run / manifest_rel).is_file():
        members.append(run / manifest_rel)
    elif final:
        raise SystemExit('error: final snapshot manifest missing')
    files, secrets = {}, []
    known = _known_secrets()
    for p in members:
        rel = str(p.relative_to(run))
        if p.is_symlink():
            files[rel] = {'symlink': os.readlink(p)}
            continue
        files[rel] = {'sha256': sha256(p), 'size': p.stat().st_size}
        data = p.read_bytes()
        text = data.decode('utf-8', 'replace')
        for name, pat in SECRET_PATTERNS.items():
            for m in pat.finditer(text):
                secrets.append({'file': rel, 'line': text.count('\n', 0, m.start()) + 1, 'pattern': name})
        for value in known:
            if value.encode() in data:
                secrets.append({'file': rel, 'line': None, 'pattern': 'known-credential-value'})
                break
    verify = verify_run(run)
    receipt = {'run_id': run.name, 'sealed_utc': utc(datetime.now(timezone.utc)), 'phase': status.get('phase'),
               'reason': status.get('reason'), 'final_snapshot': final, 'final_snapshot_manifest': manifest_rel,
               'verify': {'complete': verify['complete'], 'problems': verify['problems']},
               'file_count': len(files), 'files': files, 'secret_scan': {'findings': len(secrets)}}
    # Copy (not hardlink): the sealed directory must be independent of the working run.
    dest.mkdir(parents=True, mode=0o700)
    for p in members:
        target = dest / p.relative_to(run)
        target.parent.mkdir(parents=True, exist_ok=True)
        if p.is_symlink():
            os.symlink(os.readlink(p), target)
        else:
            shutil.copy2(p, target)
    for rel, info in files.items():  # verify the copy against the receipt
        if 'sha256' in info and sha256(dest / rel) != info['sha256']:
            raise SystemExit(f'error: copy mismatch for {rel}')
    (dest / 'secret-scan.json').write_text(json.dumps({'findings': secrets, 'patterns': sorted(SECRET_PATTERNS),
                                                       'known_credentials_checked': len(known),
                                                       'note': 'values are never printed'}, indent=2) + '\n')
    (dest / 'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    (dest / 'DVC-README.txt').write_text('Run `dvc add artifacts/runs/%s` after orchestrator review. Do not push before review.\n' % run.name)
    receipt['artifact_dir'] = str(dest)
    receipt['secret_findings'] = secrets
    return receipt


def cmd_seal(args) -> int:
    run = _run_dir(args)
    artifacts = Path(args.artifacts) if args.artifacts else _root(args) / 'artifacts'
    receipt = seal_run(run, artifacts, force=args.force)
    summary = {k: receipt[k] for k in ('run_id', 'artifact_dir', 'file_count', 'verify', 'secret_findings')}
    print(json.dumps(summary, indent=2))
    return 0 if not receipt['secret_findings'] else 2


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='wsp-harness')
    p.add_argument('--root', help='project root containing .pi/ and runs/ (default: the harness repo)')
    sub = p.add_subparsers(dest='cmd', required=True)
    from .prepare import cmd_prepare
    s = sub.add_parser('prepare-launch', help='prepare private labels and check F/G launch readiness (no launch)')
    s.add_argument('--k', type=int, required=True)
    s.add_argument('--resample', type=int, required=True)
    s.add_argument('--image', default='wsp-agent:phase1')
    s.add_argument('--proxy-image', default='wsp-proxy:phase1')
    s.set_defaults(func=cmd_prepare)
    s = sub.add_parser('launch', help='create a run and start a detached supervisor')
    s.add_argument('--arm', required=True, choices=['F', 'G', 'R', 'f', 'g', 'r'])
    s.add_argument('--k', type=int, required=True)
    s.add_argument('--labels', required=True)
    s.add_argument('--pool', required=True)
    s.add_argument('--hours', type=float, default=24.0)
    s.add_argument('--backend', choices=['simple', 'infra'], default='simple')
    s.add_argument('--test-model', action='store_true', help='allow the Haiku parent (tests only)')
    s.add_argument('--daemonizer', choices=['setsid', 'systemd'], default='setsid')
    s.add_argument('--continue-after', type=float, default=300.0)
    s.add_argument('--snapshot-interval', type=float, default=3600.0)
    s.add_argument('--status-interval', type=float, default=30.0)
    for n in ('models-dir', 'external-dir', 'hash-corpus'):
        s.add_argument('--' + n, help='infra backend only')
    s.add_argument('--image', default='wsp-agent:phase1', help='infra backend only')
    s.add_argument('--gpu-mem-cap-gib', type=float, default=11.0)
    s.set_defaults(func=cmd_launch)
    s = sub.add_parser('status'); s.add_argument('--run'); s.set_defaults(func=cmd_status)
    s = sub.add_parser('intervene'); s.add_argument('--run', required=True)
    s.add_argument('--kind', required=True, choices=['infra', 'message']); s.add_argument('--note', required=True)
    s.set_defaults(func=cmd_intervene)
    s = sub.add_parser('stop'); s.add_argument('--run', required=True); s.add_argument('--reason', required=True)
    s.set_defaults(func=cmd_stop)
    s = sub.add_parser('verify'); s.add_argument('--run', required=True); s.set_defaults(func=cmd_verify)
    s = sub.add_parser('account'); s.add_argument('--run', required=True)
    s.add_argument('--no-prices', action='store_true'); s.set_defaults(func=cmd_account)
    s = sub.add_parser('seal'); s.add_argument('--run', required=True)
    s.add_argument('--artifacts'); s.add_argument('--force', action='store_true'); s.set_defaults(func=cmd_seal)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, 'arm', None):
        args.arm = args.arm.upper()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
