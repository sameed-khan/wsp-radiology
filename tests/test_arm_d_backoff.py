import subprocess
from types import SimpleNamespace

from wsp_arms import arm_d_labels


def test_backoff_deadline_and_mixed_validation_failures(tmp_path, monkeypatch):
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config/arm-d-prompt.md').write_text('prompt')
    pool = tmp_path / 'data/pool'
    pool.mkdir(parents=True)
    (pool / 'image.png').write_bytes(b'image')
    clock = [0.0]
    sleeps = []
    calls = []
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    def fake_run(command, **kwargs):
        calls.append(kwargs['timeout'])
        if len(calls) == 1:
            return SimpleNamespace(stdout='invalid', stderr='')
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(arm_d_labels.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(arm_d_labels.time, 'sleep', sleep)
    monkeypatch.setattr(arm_d_labels.subprocess, 'run', fake_run)
    monkeypatch.setattr(arm_d_labels, 'INFRA_RETRY_SECONDS', 10)
    result = arm_d_labels.run(tmp_path, workers=1, timeout=180)
    assert sleeps == [1, 2, 4, 3]
    assert calls == [10, 10, 9, 7, 3]
    assert result['uncached'] == 1 and result['excluded'] == 0
    assert not (tmp_path / 'data/locked/private/arm-d/labels.jsonl').read_text()
