"""Unit C: CLI tests. Offline tests use a synthetic run; the WSP_LIVE=1 test uses real Docker + Haiku."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from wsp_harness import cli

FIXTURE = Path(__file__).parent / 'fixtures/harness'
live = pytest.mark.skipif(os.environ.get('WSP_LIVE') != '1', reason='paid live Haiku test')


def run_cli(root, *args, check=True):
    p = subprocess.run([sys.executable, '-m', 'wsp_harness.cli', '--root', str(root), *args],
                       capture_output=True, text=True)
    if check:
        assert p.returncode == 0, p.stderr + p.stdout
    return p


def usage(inp, out, cache=0, total=None, provider=False):
    return {'input': inp, 'output': out, 'cacheRead': cache, 'cacheWrite': 0, 'totalTokens': inp + out + cache,
            'cost': {'input': inp / 1e6, 'output': out / 1e6, 'cacheRead': 0, 'cacheWrite': 0,
                     'total': (inp + out) / 1e6, **({'totalFromProvider': True} if provider else {})}}


def msg(role, **kw):
    return {'type': 'message', 'id': 'x', 'message': {'role': role, **kw}}


def write(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r) + '\n' for r in records))


def fake_run(root, frozen=True, subagent_model='claude-haiku-5-5'):
    run = root / 'runs/R1'
    for d in ('recorder/sessions', 'recorder/subagents', 'state', 'control', 'snapshots/S1'):
        (run / d).mkdir(parents=True)
    (run / 'launch.json').write_text(json.dumps({'run_id': 'R1', 'start_utc': '2026-01-01T00:00:00Z'}))
    (run / 'interventions.jsonl').write_text(json.dumps({'kind': 'auto', 'event': 'auto-retry'}) + '\n')
    write(run / 'recorder/sessions/2026_abc.jsonl', [
        msg('assistant', provider='anthropic', model='claude-opus-5-5', usage=usage(10, 5, 100), stopReason='toolUse'),
        msg('toolResult', toolCallId='c1', toolName='bash'),
        msg('assistant', provider='anthropic', model='claude-opus-5-5', usage=usage(1, 1), stopReason='error')])
    write(run / 'recorder/rpc-events.jsonl', [{'type': 'tool_execution_end', 'toolCallId': 'c1', 'toolName': 'bash'}])
    write(run / 'recorder/rpc-receive-times.jsonl', [{'received_utc': 'x'}])
    sid = '11111111-1111-1111-1111-111111111111'
    write(run / f'recorder/subagents/{sid}.events.jsonl', [{'type': 'tool_execution_end', 'toolCallId': 'd1', 'toolName': 'read'}])
    write(run / f'recorder/subagents/2026_{sid}.jsonl', [
        msg('assistant', provider='anthropic', model=subagent_model, usage=usage(2, 2)),
        msg('toolResult', toolCallId='d1', toolName='read')])
    (run / 'snapshots/S1/manifest.json').write_text('{}')
    status = {'run_id': 'R1', 'phase': 'frozen' if frozen else 'running', 'reason': 'deadline', 'pid': 99999999,
              'updated_utc': '2026-01-01T01:00:00Z', 'final_snapshot': 'S1', 'restarts': 0, 'continuations': 2, 'snapshots': 1}
    (run / 'state/status.json').write_text(json.dumps(status))
    return run


def test_verify_account_seal(tmp_path):
    run = fake_run(tmp_path)
    v = json.loads(run_cli(tmp_path, 'verify', '--run', 'R1').stdout)
    assert v['complete'] and v['parent']['events'] == 1 and v['subagents']
    a = json.loads(run_cli(tmp_path, 'account', '--run', 'R1', '--no-prices').stdout)
    opus = a['by_model']['anthropic/claude-opus-5-5']
    assert opus['messages'] == 2 and opus['tokens']['input'] == 11 and opus['tokens']['cacheRead'] == 100
    assert opus['totalFromProvider'] is False
    assert a['by_model']['anthropic/claude-haiku-5-5']['tokens']['output'] == 2
    assert a['total']['messages'] == 3 and set(a['by_source']) == {'parent', 'subagent:11111111-1111-1111-1111-111111111111'}
    assert a['errors_and_retries']['assistant_error_messages'] == 1 and a['errors_and_retries']['auto_retry'] == 1
    assert a['wall_clock']['seconds'] == 3600 and a['gpu'] is None
    # secret in evidence -> reported without value, exit 2
    (run / 'recorder/leak.txt').write_text('key sk-ant-' + 'a' * 40 + '\n')
    p = run_cli(tmp_path, 'seal', '--run', 'R1', check=False)
    assert p.returncode == 2 and 'a' * 40 not in p.stdout
    shutil.rmtree(tmp_path / 'artifacts')
    (run / 'recorder/leak.txt').unlink()
    s = json.loads(run_cli(tmp_path, 'seal', '--run', 'R1').stdout)
    dest = tmp_path / 'artifacts/runs/R1'
    receipt = json.loads((dest / 'receipt.json').read_text())
    assert s['secret_findings'] == [] and receipt['verify']['complete']
    assert 'snapshots/S1/manifest.json' in receipt['files'] and 'launch.json' in receipt['files']
    assert 'interventions.jsonl' in receipt['files'] and 'recorder/rpc-events.jsonl' in receipt['files']
    for rel, info in receipt['files'].items():
        assert cli.sha256(dest / rel) == info['sha256']
    assert run_cli(tmp_path, 'seal', '--run', 'R1', check=False).returncode != 0  # no overwrite


def test_verify_detects_problems(tmp_path):
    run = fake_run(tmp_path, subagent_model='claude-opus-5-5')
    p = run_cli(tmp_path, 'verify', '--run', 'R1', check=False)
    v = json.loads(p.stdout)
    assert p.returncode == 1 and v['subagent_model_violations']
    write(run / 'recorder/sessions/2026_abc.jsonl', [msg('assistant', usage=usage(1, 1))])  # drop tool result
    v = json.loads(run_cli(tmp_path, 'verify', '--run', 'R1', check=False).stdout)
    assert not v['complete'] and v['parent']['missing_results']


def test_seal_requires_frozen(tmp_path):
    fake_run(tmp_path, frozen=False)
    assert run_cli(tmp_path, 'seal', '--run', 'R1', check=False).returncode != 0


def test_stop_and_intervene_infra_and_status_list(tmp_path):
    run = fake_run(tmp_path)
    run_cli(tmp_path, 'intervene', '--run', 'R1', '--kind', 'infra', '--note', 'restarted proxy')
    assert run_cli(tmp_path, 'intervene', '--run', 'R1', '--kind', 'message', '--note', 'x', check=False).returncode != 0  # frozen
    run_cli(tmp_path, 'stop', '--run', 'R1', '--reason', 'because')
    assert json.loads((run / 'control/STOP_REQUEST.json').read_text())['reason'] == 'because'
    kinds = [json.loads(l)['kind'] for l in (run / 'interventions.jsonl').read_text().splitlines()]
    assert kinds == ['auto', 'infra', 'stop']
    rows = json.loads(run_cli(tmp_path, 'status').stdout)
    assert rows[0]['run_id'] == 'R1' and rows[0]['phase'] == 'frozen' and rows[0]['supervisor_alive'] is False
    assert json.loads(run_cli(tmp_path, 'status', '--run', 'R1').stdout)['phase'] == 'frozen'


def test_message_delivery_to_fake_driver(tmp_path, sae_fixture):
    """Supervisor.deliver_messages claims the file once and steers when the agent is running."""
    from wsp_harness.supervisor import Supervisor
    root = tmp_path
    shutil.copytree(FIXTURE / '.pi', root / '.pi')
    labels, pool = root / 'labels', root / 'pool'
    labels.mkdir(); pool.mkdir(); (labels / 'labels.csv').write_text('a\n')
    from wsp_harness.run import create_run
    run = create_run(root, 'F', 1, labels, pool, 1, test_model=True)
    sup = Supervisor(run)
    sent = []

    class D:
        def send(self, c): sent.append(c)
        def prompt(self, m): sent.append({'type': 'prompt', 'message': m})
    sup.driver = D()
    (run / 'control/messages').mkdir()
    (run / 'control/messages/1.json').write_text(json.dumps({'message': 'infra notice'}))
    sup.running = True
    sup.deliver_messages(); sup.deliver_messages()
    assert [c['type'] for c in sent] == ['steer'] and sent[0]['message'] == 'infra notice'
    assert (run / 'control/messages/delivered/1.json').exists()
    (run / 'control/messages/2.json').write_text(json.dumps({'message': 'again'}))
    sup.running = False
    sup.send_prompt = lambda t: sent.append({'type': 'prompt', 'message': t})
    sup.deliver_messages()
    assert sent[-1] == {'type': 'prompt', 'message': 'again'} and sup.messages_delivered == 2
    assert [json.loads(l)['event'] for l in (run / 'interventions.jsonl').read_text().splitlines()] == ['message-delivered'] * 2


def test_phase1_image_defaults():
    parser = cli.build_parser()
    prepare = parser.parse_args(['prepare-launch', '--k', '10', '--resample', '1'])
    launch = parser.parse_args(['launch', '--arm', 'F', '--k', '10', '--labels', '/l', '--pool', '/p'])
    assert (prepare.image, prepare.proxy_image, launch.image) == (
        'wsp-agent:phase1', 'wsp-proxy:phase1', 'wsp-agent:phase1')
    from infra.sandbox import DEFAULT_PROXY_IMAGE
    assert DEFAULT_PROXY_IMAGE == prepare.proxy_image


def test_infra_helper_argv(tmp_path):
    from wsp_harness import sandbox_infra
    (tmp_path / 'state').mkdir()
    (tmp_path / 'state/backend.json').write_text(json.dumps({'hash_corpus': '/c', 'gpu_mem_cap_gib': 11.0}))
    w, g = sandbox_infra.helper_argv(tmp_path, 'wsp-agent-x')
    assert w[1:4] == ['-m', 'infra.watcher', '--workspace'] and '--control-dir' in w
    assert g[-2:] == ['--sandbox-json', str(tmp_path / 'state/sandbox.json')] and '--state-dir' in g


@live
def test_live_launch_detached(tmp_path):
    shutil.copytree(FIXTURE / '.pi', tmp_path / '.pi')
    (tmp_path / '.pi/prompts/wsp-launch.md').write_text(
        'Use bash to run `sleep 30`, then use the write tool to write /workspace/output/a.txt containing hi, then '
        'use the subagent tool with wait=true and task "run hostname with bash and report it", then reply "done" and stop. '
        'Do NOT create output/FINAL.')
    (tmp_path / '.pi/prompts/wsp-continue.md').write_text(
        'Harness notice at {now_utc}; remaining {remaining}. If nothing more to do reply "ok" only. Do NOT create output/FINAL.')
    labels, pool = tmp_path / 'labels', tmp_path / 'pool'
    labels.mkdir(); pool.mkdir()
    (labels / 'labels.csv').write_text('image,patient,label\n')
    # The launching process exits immediately; the supervisor must survive it.
    launcher = subprocess.run(
        [sys.executable, '-c',
         'import sys; from wsp_harness.cli import main; sys.exit(main(sys.argv[1:]))',
         '--root', str(tmp_path), 'launch', '--arm', 'F', '--k', '10', '--labels', str(labels), '--pool', str(pool),
         '--hours', '0.05', '--backend', 'simple', '--test-model', '--continue-after', '30',
         '--snapshot-interval', '60', '--status-interval', '3'], capture_output=True, text=True)
    assert launcher.returncode == 0, launcher.stderr
    run_id = launcher.stdout.strip().splitlines()[-1]
    run = tmp_path / 'runs' / run_id
    pid = int((run / 'state/supervisor.pid').read_text())
    assert cli._pid_alive(pid)
    st = json.loads(run_cli(tmp_path, 'status', '--run', run_id).stdout)
    assert st['supervisor_alive'] and st['phase'] in ('starting', 'running', 'idle')
    assert run_id in [r['run_id'] for r in json.loads(run_cli(tmp_path, 'status').stdout)]
    # steer message while the agent sleeps in bash
    time.sleep(10)
    run_cli(tmp_path, 'intervene', '--run', run_id, '--kind', 'message',
            '--note', 'Infrastructure notice: the file system was briefly remounted; no action is needed.')
    run_cli(tmp_path, 'intervene', '--run', run_id, '--kind', 'infra', '--note', 'test infra note')
    end = time.time() + 240
    while time.time() < end and cli._pid_alive(pid):
        time.sleep(3)
    assert not cli._pid_alive(pid)
    st = json.loads(run_cli(tmp_path, 'status', '--run', run_id).stdout)
    assert st['phase'] == 'frozen' and st['reason'] == 'deadline' and not st['supervisor_alive']
    assert st['messages_delivered'] == 1
    events = [json.loads(l) for l in (run / 'interventions.jsonl').read_text().splitlines()]
    assert {e['kind'] for e in events} >= {'message', 'infra', 'auto'}
    assert any(e['event'] == 'message-delivered' for e in events)
    assert 'Infrastructure notice' in (run / 'recorder/rpc-events.jsonl').read_text()
    assert (run / 'workspace/output/a.txt').read_text().strip() == 'hi'
    assert not subprocess.run(['docker', 'ps', '-a', '--filter', f'name={run_id}', '--format', '{{.Names}}'],
                              capture_output=True, text=True).stdout.strip()
    v = run_cli(tmp_path, 'verify', '--run', run_id, check=False)
    report = json.loads(v.stdout)
    assert report['complete'], report
    assert report['parent']['events'] >= 2 and report['subagents'], report
    a = json.loads(run_cli(tmp_path, 'account', '--run', run_id).stdout)
    assert 'anthropic/claude-haiku-5-5' in a['by_model'] and a['total']['tokens']['output'] > 0
    assert a['by_model']['anthropic/claude-haiku-5-5']['totalFromProvider'] is False
    assert a['price_table']['models'].get('anthropic/claude-haiku-5-5')
    assert any(k.startswith('subagent:') for k in a['by_source'])
    s = run_cli(tmp_path, 'seal', '--run', run_id, check=False)
    assert s.returncode == 0, s.stdout + s.stderr
    dest = tmp_path / 'artifacts/runs' / run_id
    receipt = json.loads((dest / 'receipt.json').read_text())
    assert receipt['verify']['complete'] and receipt['final_snapshot'] == st['final_snapshot']
    for rel, info in receipt['files'].items():
        assert cli.sha256(dest / rel) == info['sha256']


@live
def test_live_stop_systemd(tmp_path):
    if not shutil.which('systemd-run'):
        pytest.skip('no systemd-run')
    shutil.copytree(FIXTURE / '.pi', tmp_path / '.pi')
    (tmp_path / '.pi/prompts/wsp-launch.md').write_text('Use bash to run `sleep 60`, then reply "done" and stop.')
    labels, pool = tmp_path / 'labels', tmp_path / 'pool'
    labels.mkdir(); pool.mkdir(); (labels / 'labels.csv').write_text('image,patient,label\n')
    out = run_cli(tmp_path, 'launch', '--arm', 'f', '--k', '1', '--labels', str(labels), '--pool', str(pool),
                  '--hours', '0.5', '--test-model', '--daemonizer', 'systemd', '--status-interval', '2').stdout
    run_id = out.strip().splitlines()[-1]
    run = tmp_path / 'runs' / run_id
    pid = int((run / 'state/supervisor.pid').read_text())
    try:
        end = time.time() + 60
        while time.time() < end and json.loads(run_cli(tmp_path, 'status', '--run', run_id).stdout).get('tool_calls', 0) < 0:
            time.sleep(1)
        time.sleep(8)
        assert cli._pid_alive(pid)
        run_cli(tmp_path, 'stop', '--run', run_id, '--reason', 'live stop test')
        end = time.time() + 90
        while time.time() < end and cli._pid_alive(pid):
            time.sleep(1)
        st = json.loads(run_cli(tmp_path, 'status', '--run', run_id).stdout)
        assert st['phase'] == 'frozen' and st['reason'] == 'stop-request: live stop test', st
        assert not subprocess.run(['docker', 'ps', '-a', '--filter', f'name={run_id}', '--format', '{{.Names}}'],
                                  capture_output=True, text=True).stdout.strip()
        assert json.loads(run_cli(tmp_path, 'verify', '--run', run_id, check=False).stdout)['parent']['complete']
    finally:
        subprocess.run(['systemctl', '--user', 'stop', f'wsp-run-{run_id}.service'], capture_output=True)
