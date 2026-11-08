"""Unit B: opt-in paid Docker/Haiku lifecycle tests."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time

import pytest

from wsp_harness.run import create_run
from wsp_harness.supervisor import Supervisor

FIXTURE = Path(__file__).parent / 'fixtures/harness'
live = pytest.mark.skipif(os.environ.get('WSP_LIVE') != '1', reason='paid live Haiku test')


@pytest.fixture(autouse=True)
def package(sae_fixture):
    pass


def setup(tmp_path, prompt, hours):
    shutil.copytree(FIXTURE / '.pi', tmp_path / '.pi')
    (tmp_path / '.pi/prompts/wsp-launch.md').write_text(prompt)
    (tmp_path / '.pi/prompts/wsp-continue.md').write_text(
        'Harness notice at {now_utc}; deadline {deadline_utc}; remaining {remaining}. If you have nothing more to do, reply "ok" only. Do NOT create output/FINAL.')
    labels, pool = tmp_path / 'labels', tmp_path / 'pool'
    labels.mkdir(); pool.mkdir()
    (labels / 'labels.csv').write_text('image,patient,label\n')
    return create_run(tmp_path, 'F', 10, labels, pool, hours, test_model=True)


def containers():
    return subprocess.run(['docker', 'ps', '-a', '--filter', 'name=wsp-agent-', '--format', '{{.Names}}'],
                          capture_output=True, text=True).stdout.split()


def interventions(run):
    return [json.loads(l) for l in (run / 'interventions.jsonl').read_text().splitlines()]


@live
def test_deadline_continuation_snapshot(tmp_path):
    run = setup(tmp_path, 'Use the write tool to write /workspace/output/a.txt containing hi, then reply "done" and stop. Do NOT create FINAL.', 0.05)
    sup = Supervisor(run, continue_after=30, snapshot_interval=60, status_interval=5)
    t0 = time.time()
    reason = sup.run_all()
    elapsed = time.time() - t0
    assert reason == 'deadline'
    assert 170 <= elapsed <= 215, elapsed
    status = json.loads((run / 'state/status.json').read_text())
    assert status['phase'] == 'frozen' and status['reason'] == 'deadline'
    assert status['continuations'] >= 1 and status['snapshots'] >= 2  # >=1 periodic + final
    assert status['turns'] >= 2 and status['tool_calls'] >= 1
    kinds = [i['event'] for i in interventions(run)]
    assert 'auto-continuation' in kinds
    assert all(i['kind'] == 'auto' for i in interventions(run))
    assert (run / 'workspace/output/a.txt').read_text().strip() == 'hi'
    assert not [c for c in containers() if run.name in c]
    final = run / 'snapshots' / status['final_snapshot']
    assert (final / 'manifest.json').exists() and (final / 'workspace/output/a.txt').exists()
    assert len(list((run / 'snapshots').iterdir())) == status['snapshots']
    log = (run / 'recorder/rpc-events.jsonl').read_text()
    assert log.count('"auto-continuation"') == 0  # continuation is a prompt, logged by supervisor
    assert 'Harness notice' in log


@live
def test_crash_restart_and_stop_request(tmp_path):
    run = setup(tmp_path, 'Use bash to run `sleep 20; echo x`, then reply "done" and stop. Do NOT create FINAL.', 0.2)
    sup = Supervisor(run, continue_after=15, snapshot_interval=3600, status_interval=2, retry_base=1)
    out = {}
    th = threading.Thread(target=lambda: out.update(reason=sup.run_all()))
    th.start()
    deadline = time.time() + 60
    while time.time() < deadline and not (sup.driver and sup.tool_calls + sup.turns >= 1):
        time.sleep(0.5)
    first_session = sorted((run / 'recorder/sessions').glob('*.jsonl'))
    assert first_session
    os.killpg(sup.driver.process.pid, signal.SIGKILL)  # crash pi
    deadline = time.time() + 90
    while time.time() < deadline and sup.restarts < 1:
        time.sleep(0.5)
    assert sup.restarts == 1
    time.sleep(8)
    (run / 'control').mkdir(exist_ok=True)
    (run / 'control/STOP_REQUEST.json').write_text(json.dumps({'reason': 'test stop'}))
    th.join(60)
    assert not th.is_alive()
    assert out['reason'] == 'stop-request: test stop'
    status = json.loads((run / 'state/status.json').read_text())
    assert status['phase'] == 'frozen' and status['retries'] >= 1 and status['restarts'] == 1
    assert [i for i in interventions(run) if i['event'] == 'auto-retry']
    sessions = list((run / 'recorder/sessions').glob('*.jsonl'))
    assert len(sessions) == len(first_session)  # resumed the same session file
    assert not [c for c in containers() if run.name in c]
