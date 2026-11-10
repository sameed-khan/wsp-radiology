"""Live cutover exercises the same persistent session and sandbox."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime

import pytest

ROOT = Path('/home/skhanxx8/projects/wsp-radiology')
FIXTURE = Path(__file__).parent / 'fixtures/harness/.pi'


@pytest.mark.skipif(os.environ.get('WSP_LIVE') != '1', reason='paid live test')
@pytest.mark.parametrize('backend', ['simple', 'infra'])
def test_cutover(tmp_path, sae_fixture, backend):
    shutil.copytree(FIXTURE, tmp_path / '.pi')
    network = '; curl -sI https://pypi.org/simple/ >/workspace/output/proxy-check' if backend == 'infra' else ''
    (tmp_path / '.pi/prompts/wsp-launch.md').write_text('Use bash to run echo BEFORE_CUTOVER > /workspace/output/before; then reply done. Never create FINAL.')
    (tmp_path / '.pi/prompts/wsp-continue.md').write_text('Use bash to run echo AFTER_CUTOVER > /workspace/output/after' + network + '; then reply done. Never create FINAL.')
    labels = tmp_path / 'labels'; labels.mkdir()
    (labels / 'labels.csv').write_text('image,patient,label\n')
    pool = tmp_path / 'pool'; pool.mkdir()
    def cli(*args):
        return subprocess.run([sys.executable, '-m', 'wsp_harness.cli', '--root', str(tmp_path), *args], capture_output=True, text=True, timeout=120)
    args = ['launch', '--arm', 'F', '--k', '10', '--labels', str(labels), '--pool', str(pool), '--backend', backend, '--hours', '0.1', '--test-model', '--status-interval', '2']
    if backend == 'infra':
        args += ['--models-dir', str(ROOT / 'models'), '--external-dir', str(ROOT / 'data/external/extracted'), '--hash-corpus', str(ROOT / 'data/locked/private/hash-corpus.json')]
    launched = cli(*args)
    assert launched.returncode == 0, launched.stderr
    run = tmp_path / 'runs' / launched.stdout.strip().splitlines()[-1]
    status = {}
    try:
        end = time.time() + 110
        while time.time() < end:
            events = (run / 'recorder/rpc-events.jsonl')
            if events.exists() and (run / 'workspace/output/before').exists() and list((run / 'recorder/sessions').glob('*.jsonl')):
                break
            time.sleep(1)
        else:
            pytest.fail('initial tool call did not occur')
        time.sleep(60)
        sessions = list((run / 'recorder/sessions').glob('*.jsonl'))
        before = [json.loads(x) for x in sessions[0].read_text().splitlines()]
        detached = cli('detach', '--run', run.name)
        assert detached.returncode == 0, detached.stderr
        status = json.loads((run / 'state/status.json').read_text())
        assert status['phase'] == 'detached' and not (run / 'state/final-snapshot.json').exists()
        container = status['container']
        assert subprocess.check_output(['docker', 'inspect', '--format', '{{.State.Running}}', container], text=True).strip() == 'true'
        extension = cli('extend', '--run', run.name, '--seconds', '5', '--reason', 'test cutover')
        assert extension.returncode == 0
        adopted = cli('adopt', '--run', run.name)
        assert adopted.returncode == 0, adopted.stderr
        assert subprocess.check_output(['docker', 'inspect', '--format', '{{.State.Running}}', container], text=True).strip() == 'true'
        if backend == 'infra':
            ps = subprocess.check_output(['ps', '-eo', 'args='], text=True)
            assert str(run / 'state/watcher') in ps and str(run / 'state/sandbox.json') in ps
        end = time.time() + 440
        while time.time() < end:
            status = json.loads((run / 'state/status.json').read_text())
            if status['phase'].startswith('frozen'):
                break
            time.sleep(2)
        assert status['phase'] == 'frozen' and status['reason'] == 'deadline', status
        assert status['extensions_seconds'] == 5
        assert datetime.fromisoformat(status['updated_utc'].replace('Z', '+00:00')) >= datetime.fromisoformat(status['deadline_utc'].replace('Z', '+00:00'))
        records = [json.loads(x) for x in (run / 'interventions.jsonl').read_text().splitlines()]
        assert {'supervisor-adopted', 'supervisor-detached'} <= {x['event'] for x in records if x['kind'] == 'infra'}
        assert list((run / 'recorder/sessions').glob('*.jsonl')) == sessions
        after = [json.loads(x) for x in sessions[0].read_text().splitlines()]
        ids = {x.get('id') for x in before if x.get('id')}
        assert any(x.get('parentId') in ids for x in after[len(before):])
        events = (run / 'recorder/rpc-events.jsonl').read_text()
        assert 'AFTER_CUTOVER' in events
        assert (run / 'workspace/output/after').read_text().strip() == 'AFTER_CUTOVER'
        assert cli('verify', '--run', run.name).returncode == 0
        if backend == 'infra':
            assert (run / 'state/watcher.log').exists() and (run / 'state/gpu_watchdog.log').exists()
            assert (run / 'state/sandbox.json').exists()
            assert '200' in (run / 'workspace/output/proxy-check').read_text()
            assert list((run / 'state/proxy').glob('*.jsonl'))
    finally:
        if not str(status.get('phase', '')).startswith('frozen'):
            cli('stop', '--run', run.name, '--reason', 'test cleanup')


def test_legacy_input_hashes_and_status_restore(tmp_path):
    from wsp_harness.config import load_inputs
    from wsp_harness.supervisor import Supervisor
    shutil.copytree(FIXTURE, tmp_path / '.pi')
    inputs = load_inputs(tmp_path, 'F', allow_test_model=True)
    hashes = dict(inputs.hashes); del hashes['extension']
    (tmp_path / '.pi/prompts/wsp-extension.md').unlink()
    run = tmp_path / 'runs/r'; (run / 'state').mkdir(parents=True); (run / 'recorder').mkdir()
    (run / 'launch.json').write_text(json.dumps({'run_id': 'r', 'arm': 'F', 'test_model': True, 'input_hashes': hashes,
        'deadline_epoch': 9999999999, 'deadline_utc': '2286-11-20T17:46:39Z', 'start_utc': '2026-01-01T00:00:00Z'}))
    (run / 'state/status.json').write_text(json.dumps({'phase': 'detached', 'turns': 9, 'tool_calls': 7}))
    sup = Supervisor(run, adopt=True)
    assert sup.turns == 9 and sup.tool_calls == 7
    # Interrupted outages must not leave the subagent deadline suspended.
    from types import SimpleNamespace
    (run / 'control').mkdir()
    (run / 'interventions.jsonl').touch()
    (run / 'state/rate-limit-outage.json').write_text('{"start_epoch": 1}')
    sup.backend = SimpleNamespace(adopt=lambda _: 'wsp-agent-r')
    sup.kill_processes = lambda: None
    sup.start_pi = lambda resume: None
    sup.send_prompt = lambda _: None
    sup.continuation_text = lambda: 'continue'
    sup.run_loop = lambda: 'detached'
    assert sup.run_all() == 'detached'
    assert not (run / 'state/rate-limit-outage.json').exists()
    assert len(list((run / 'state').glob('rate-limit-outage-interrupted-*.json'))) == 1
    sup.log_file.close()
    (tmp_path / '.pi/prompts/wsp-continue.md').write_text('tampered')
    with pytest.raises(RuntimeError, match='inputs changed'):
        Supervisor(run, adopt=True)
