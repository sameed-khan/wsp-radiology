"""Unit D: opt-in (WSP_LIVE=1) paid end-to-end test with real Docker + Haiku.

Parent Haiku uses bash, write, an image read, one synchronous and one
asynchronous subagent; then containment, subagent models and `verify` are
checked.
"""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import threading
import time
import zlib

import pytest

from wsp_harness.run import create_run, REPO
from wsp_harness.supervisor import Supervisor

FIXTURE = Path(__file__).parent / 'fixtures/harness'
ROOT = Path('/home/skhanxx8/projects/wsp-radiology')
live = pytest.mark.skipif(os.environ.get('WSP_LIVE') != '1', reason='paid live Haiku test')


def red_png() -> bytes:
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data))
    row = b'\x00' + b'\xff\x00\x00' * 32
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 32, 32, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(row * 32)) + chunk(b'IEND', b''))


PROMPT = (
    'Do these steps in order using tools. 1) bash: run `hostname`. 2) write tool: write /workspace/output/x.txt '
    'containing the hostname. 3) read tool: read the image /inputs/pool/red.png and write its dominant colour name '
    '(one word) to /workspace/output/colour.txt. 4) subagent tool with wait=true, task "run `echo sync-child` with bash '
    'and report the output". 5) subagent tool with wait=false, task "write /workspace/output/async.txt containing '
    'async-ok using the write tool, then report done"; then call subagent_result with that id and wait=true. '
    '6) bash: `touch /workspace/output/steps-done; sleep 45`. Then reply "done" and stop. Do NOT create output/FINAL.')


def sh(container, script):
    return subprocess.run(['docker', 'exec', '--user', '1004:1004', container, 'sh', '-c', script],
                          capture_output=True, text=True)


@live
def test_end_to_end(tmp_path):
    shutil.copytree(FIXTURE / '.pi', tmp_path / '.pi')
    (tmp_path / '.pi/prompts/wsp-launch.md').write_text(PROMPT)
    (tmp_path / '.pi/prompts/wsp-continue.md').write_text(
        'Harness notice {now_utc}; remaining {remaining}. If nothing more to do reply "ok" only. Do NOT create output/FINAL.')
    labels, pool = tmp_path / 'labels', tmp_path / 'pool'
    labels.mkdir(); pool.mkdir()
    (labels / 'labels.csv').write_text('image,patient,label\n')
    (pool / 'red.png').write_bytes(red_png())
    run = create_run(tmp_path, 'F', 10, labels, pool, 0.12, test_model=True)
    sup = Supervisor(run, continue_after=120, snapshot_interval=3600, status_interval=5)
    out = {}
    th = threading.Thread(target=lambda: out.update(reason=sup.run_all()))
    th.start()
    try:
        marker = run / 'workspace/output/steps-done'
        end = time.time() + 180
        while time.time() < end and not marker.exists() and th.is_alive():
            time.sleep(1)
        assert marker.exists(), 'agent did not finish the steps'
        container = 'wsp-agent-' + run.name

        # --- containment, checked from inside the running container ---
        locked = ROOT / 'data/locked'
        forbidden = [str(Path.home() / '.pi'), str(run / 'recorder'), str(run), str(REPO / 'harness'),
                     str(REPO), '/var/run/docker.sock', '/run/docker.sock', str(locked), str(ROOT / 'data'),
                     str(ROOT), str(Path.home())]
        for path in forbidden:
            r = sh(container, f'test -e "{path}"')
            assert r.returncode != 0, f'{path} reachable from the container'
        r = sh(container, 'echo "HOME=$HOME"; ls -la "$HOME"; find / -xdev \\( -name "docker.sock" -o -name ".pi" \\) 2>/dev/null; '
                          'find /proc/self/root -maxdepth 0 >/dev/null; env')
        assert 'docker.sock' not in r.stdout and '/.pi' not in r.stdout
        env = sh(container, 'env').stdout
        assert not any(k in env for k in ('ANTHROPIC_API_KEY', 'EXA_API_KEY', 'OPENAI_API_KEY', 'WSP_RECORDER_DIR', 'WSP_CONTAINER'))
        mounts = json.loads(subprocess.check_output(['docker', 'inspect', container, '--format', '{{json .Mounts}}']))
        assert sorted(m['Destination'] for m in mounts) == ['/inputs/labels', '/inputs/pool', '/workspace']
        assert not any('locked' in m['Source'] or m['Source'].endswith('/recorder') for m in mounts)
        assert sh(container, 'find /sys/class/net -mindepth 1 -maxdepth 1 | grep -v lo$ ; true').stdout.strip() == ''
        assert sh(container, 'touch /usr/x').returncode != 0  # read-only rootfs
        assert sh(container, 'touch /inputs/pool/x').returncode != 0  # pool read-only
        assert sh(container, 'touch /workspace/output/ok').returncode == 0
        # the agent's own filesystem view through the harness bash tool path (same container/user)
        assert sh(container, 'id -u').stdout.strip() == '1004'
    finally:
        (run / 'control').mkdir(exist_ok=True)
        (run / 'control/STOP_REQUEST.json').write_text(json.dumps({'reason': 'e2e test done'}))
        th.join(120)
    assert not th.is_alive()
    assert out['reason'].startswith('stop-request')

    # --- agent work ---
    output = run / 'workspace/output'
    assert (output / 'x.txt').read_text().strip() == 'wsp-agent-' + run.name
    assert 'red' in (output / 'colour.txt').read_text().lower()
    assert (output / 'async.txt').read_text().strip() == 'async-ok'
    events = [json.loads(l) for l in (run / 'recorder/rpc-events.jsonl').read_text().splitlines()]
    starts = [e for e in events if e.get('type') == 'tool_execution_start']
    names = [e['toolName'] for e in starts]
    for tool in ('bash', 'write', 'read', 'subagent', 'subagent_result'):
        assert tool in names, names
    assert any(e['toolName'] == 'read' and str(e['args'].get('path', '')).endswith('red.png') for e in starts)
    ends = [e for e in events if e.get('type') == 'tool_execution_end' and e.get('toolName') == 'read']
    assert any('image' in json.dumps(e) for e in ends), 'image attachment not returned by read'
    waits = {e['args'].get('wait', True) for e in starts if e['toolName'] == 'subagent'}
    assert waits == {True, False}

    # --- subagent sessions: recorded, Haiku only ---
    sub = run / 'recorder/subagents'
    sessions = [p for p in sub.glob('*.jsonl') if not p.name.endswith('.events.jsonl')]
    assert len(sessions) == 2 and len(list(sub.glob('*.events.jsonl'))) == 2
    for s in sessions:
        msgs = [e['message'] for e in map(json.loads, s.read_text().splitlines())
                if e.get('type') == 'message' and e['message'].get('role') == 'assistant']
        assert msgs and all(m['model'] == 'claude-haiku-5-5' and m['provider'] == 'anthropic' for m in msgs)

    # --- verify / account via the CLI ---
    def cli(*a):
        return subprocess.run([sys.executable, '-m', 'wsp_harness.cli', '--root', str(tmp_path), *a],
                              capture_output=True, text=True)
    v = cli('verify', '--run', run.name)
    assert v.returncode == 0, v.stdout + v.stderr
    report = json.loads(v.stdout)
    assert report['complete'] and len(report['subagents']) == 2 and not report['subagent_model_violations']
    a = json.loads(cli('account', '--run', run.name, '--no-prices').stdout)
    assert 'anthropic/claude-haiku-5-5' in a['by_model'] and len(a['by_source']) == 3
    status = json.loads((run / 'state/status.json').read_text())
    assert status['phase'] == 'frozen'
    containers = subprocess.run(['docker', 'ps', '-a', '--filter', 'name=' + run.name, '--format', '{{.Names}}'],
                                capture_output=True, text=True).stdout.split()
    assert not containers
