import json
import os
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from wsp_harness import deadline
from wsp_harness.cli import main
from wsp_harness.supervisor import Supervisor, is_rate_limit
from test_harness_supervisor import setup


@pytest.mark.parametrize('text', ['HTTP 429', 'rate_limit_error', 'RATE LIMIT', 'usage limit', 'Overloaded', '529',
                                  'Claude usage limit reached. Your limit will reset at 5pm',
                                  'Quota exceeded for this period', 'Too Many Requests', 'Please try again later.'])
def test_classification(text):
    assert is_rate_limit(text)
    assert not is_rate_limit('connection reset')


def test_accounting_and_cli(tmp_path):
    run = tmp_path / 'runs/r'; (run / 'state').mkdir(parents=True)
    (run / 'launch.json').write_text('{}')
    (run / 'interventions.jsonl').touch()
    assert main(['--root', str(tmp_path), 'extend', '--run', 'r', '--seconds', '4.25', '--reason', 'outage']) == 0
    assert deadline.total(run) == 4.25
    assert json.loads((run / 'interventions.jsonl').read_text())['kind'] == 'infra'
    for seconds in (0, -1, float('nan'), float('inf')):
        with pytest.raises(ValueError):
            deadline.append(run, {'seconds': seconds})


def test_repeated_failure_accounted_once(tmp_path, monkeypatch):
    (tmp_path / 'state').mkdir()
    (tmp_path / 'interventions.jsonl').touch()
    sup = Supervisor.__new__(Supervisor)
    sup.run = tmp_path
    sup.original_deadline = 1000
    sup.outage_start = None
    sup.running = True
    sup.messages_delivered = 0
    sup.log = lambda _: None
    sent = []
    sup.driver = SimpleNamespace(send=sent.append)
    sup.inputs = SimpleNamespace(extension_template='{lost} {deadline_utc} {remaining}')
    clock = iter([100.0, 110.0, 140.25])
    monkeypatch.setattr(time, 'time', lambda: next(clock))
    for error in ('429 rate limit', '529 overloaded'):
        sup.handle_event({'type': 'message_end', 'message': {'role': 'assistant', 'stopReason': 'error', 'errorMessage': error}})
    sup.handle_event({'type': 'message_end', 'message': {'role': 'assistant', 'stopReason': 'stop'}})
    entries = [json.loads(line) for line in (tmp_path / 'state/deadline-extensions.jsonl').read_text().splitlines()]
    assert len(entries) == 1 and entries[0]['seconds'] == 40.25
    assert sup.deadline == 1040.25 and sup.outage_start is None
    assert json.loads((tmp_path / 'state/deadline.json').read_text())['extensions_seconds'] == 40.25
    assert not (tmp_path / 'state/rate-limit-outage.json').exists()
    assert sent[0]['type'] == 'steer' and sent[0]['message'].startswith('0:00:40')


@pytest.mark.skipif(os.environ.get('WSP_LIVE') != '1', reason='paid live Haiku test')
def test_live_extensions(tmp_path, sae_fixture, monkeypatch):
    monkeypatch.setenv('WSP_TEST_429_FAILURES', '4')
    run = setup(tmp_path, 'Reply ok only. Do not create FINAL.', 0.05)
    sup = Supervisor(run, continue_after=300, snapshot_interval=3600, status_interval=1, retry_base=2.7, tick=0.2)
    out = {}
    thread = threading.Thread(target=lambda: out.update(reason=sup.run_all()))
    thread.start()
    try:
        until = time.time() + 110
        while time.time() < until and (not (run / 'state/deadline-extensions.jsonl').exists()) and thread.is_alive():
            time.sleep(0.5)
        entries = [json.loads(x) for x in (run / 'state/deadline-extensions.jsonl').read_text().splitlines()]
        assert len(entries) == 1 and 37 <= entries[0]['seconds'] <= 70
        assert main(['--root', str(tmp_path), 'extend', '--run', run.name, '--seconds', '5', '--reason', 'test']) == 0
        thread.join(260)
        assert not thread.is_alive()
        assert out['reason'] == 'deadline'
        status = json.loads((run / 'state/status.json').read_text())
        assert status['phase'] == 'frozen'
        assert status['extensions_seconds'] == pytest.approx(entries[0]['seconds'] + 5)
        frozen = datetime.fromisoformat(status['updated_utc'].replace('Z', '+00:00')).timestamp()
        assert frozen >= sup.original_deadline + status['extensions_seconds']
        assert 'Infrastructure notice' in (run / 'recorder/rpc-events.jsonl').read_text()
    finally:
        if thread.is_alive():
            (run / 'control/STOP_REQUEST.json').write_text('{"reason":"cleanup"}')
            thread.join(60)


def test_retry_policy_meets_five_hour_requirement():
    import inspect
    sig = inspect.signature(Supervisor.__init__)
    cap = sig.parameters['retry_cap'].default
    assert cap <= 1800  # at least one retry every 30 min
    # no attempt limit: retries continue for any outage length (>= 5 h)
    src = inspect.getsource(Supervisor)
    assert 'max_retries' not in src
    assert 'now >= self.deadline and self.outage_start is None' in src  # no freeze during an open outage
