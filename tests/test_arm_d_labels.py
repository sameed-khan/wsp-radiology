import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from wsp_arms import arm_d_labels


@pytest.mark.parametrize('text', ['{}', '{"p_monteggia":true}', '{"p_monteggia":101}', '{"p_monteggia":NaN}', '{"p_monteggia":1.5}', '{"p_monteggia":1,"x":2}', '```json\n{}\n```'])
def test_invalid_response(text):
    with pytest.raises(ValueError):
        arm_d_labels.parse_response(text)


def test_cache_retry_and_resume(tmp_path, monkeypatch):
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config/arm-d-prompt.md').write_text('prompt')
    pool = tmp_path / 'data/pool'
    pool.mkdir(parents=True)
    for i in range(3):
        (pool / f'{i}.png').write_bytes(b'image')
    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout='bad' if len(calls) == 1 else '{"p_monteggia":50}')
    monkeypatch.setattr(arm_d_labels.subprocess, 'run', fake_run)
    result = arm_d_labels.run(tmp_path, workers=1)
    assert result['new'] == 3 and result['failed'] == 0 and len(calls) == 4
    assert arm_d_labels.run(tmp_path, workers=1)['new'] == 0
    cache = tmp_path / 'data/locked/private/arm-d/labels.jsonl'
    assert cache.stat().st_mode & 0o777 == 0o600
    assert len([json.loads(s) for s in cache.read_text().splitlines()]) == 3
    (pool / '0.png').write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        arm_d_labels.run(tmp_path)
