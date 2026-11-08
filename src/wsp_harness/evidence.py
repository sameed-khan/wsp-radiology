"""Host-only evidence primitives. These are not a run supervisor.

Callers must stop workspace writers before a final snapshot and must prevent
concurrent snapshot creation. Periodic snapshots are necessarily point-in-time
approximations when writers are active.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

CHECKPOINT_SUFFIXES = {'.pt', '.pth', '.safetensors', '.bin', '.ckpt', '.npz', '.npy'}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def snapshot(workspace: Path, snapshots: Path) -> Path:
    """Copy using rsync link-dest, then manifest regular files and symlinks.

    A new directory is atomically published only after successful copying and
    hashing. Workspace symlinks are recorded but never traversed.
    """
    workspace, snapshots = workspace.resolve(strict=True), snapshots.resolve()
    if not workspace.is_dir() or snapshots == workspace or workspace in snapshots.parents:
        raise ValueError('snapshots must be outside the workspace')
    snapshots.mkdir(parents=True, exist_ok=True, mode=0o700)
    previous = sorted(p for p in snapshots.iterdir() if p.is_dir() and not p.name.startswith('.'))
    temp = Path(tempfile.mkdtemp(prefix='.snapshot-', dir=snapshots))
    try:
        data = temp / 'workspace'
        data.mkdir()
        command = ['rsync', '-a', '--checksum']
        if previous:
            command += ['--link-dest', str(previous[-1] / 'workspace')]
        subprocess.run([*command, str(workspace) + '/', str(data) + '/'], check=True)
        manifest, checkpoints = [], []
        for path in sorted(data.rglob('*')):
            rel = path.relative_to(data).as_posix()
            if path.is_symlink():
                manifest.append({'path': rel, 'type': 'symlink', 'target': os.readlink(path)})
            elif path.is_file():
                item = {'path': rel, 'type': 'file', 'size': path.stat().st_size, 'sha256': sha256(path)}
                manifest.append(item)
                if path.suffix.lower() in CHECKPOINT_SUFFIXES and item['size'] > 1024 * 1024:
                    checkpoints.append(item)
            elif not path.is_dir():
                raise ValueError(f'unsupported special file in snapshot: {rel}')
        _json(temp / 'manifest.json', manifest)
        _json(temp / 'checkpoints.json', checkpoints)
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        dest = snapshots / name
        os.rename(temp, dest)
        return dest
    except BaseException:
        import shutil
        shutil.rmtree(temp, ignore_errors=True)
        raise


def _records(path: Path):
    with path.open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError('record is not an object')
            except (ValueError, UnicodeError) as exc:
                raise ValueError(f'invalid JSONL in {path}:{number}') from exc
            yield record


def verify_events(event_file: Path, session_files: list[Path]) -> dict:
    """Compare event and persisted result multiplicities, including tool names.

    Call separately for the parent and for each child: tool call IDs are not
    guaranteed globally unique. Missing streams/sessions are errors, not success.
    """
    if not session_files:
        raise ValueError('no session files')
    events = Counter()
    results = Counter()
    for event in _records(event_file):
        if event.get('type') == 'tool_execution_end':
            if not isinstance(event.get('toolCallId'), str) or not isinstance(event.get('toolName'), str):
                raise ValueError('malformed tool execution event')
            events[(event['toolCallId'], event['toolName'])] += 1
    for file in session_files:
        for entry in _records(file):
            msg = entry.get('message', {})
            if entry.get('type') == 'message' and isinstance(msg, dict) and msg.get('role') == 'toolResult':
                if not isinstance(msg.get('toolCallId'), str) or not isinstance(msg.get('toolName'), str):
                    raise ValueError('malformed tool result')
                results[(msg['toolCallId'], msg['toolName'])] += 1
    def differences(counter):
        return [{'toolCallId': key[0], 'toolName': key[1], 'count': count} for key, count in sorted(counter.items())]
    return {'complete': events == results, 'events': sum(events.values()), 'results': sum(results.values()),
            'missing_results': differences(events - results), 'missing_events': differences(results - events)}
