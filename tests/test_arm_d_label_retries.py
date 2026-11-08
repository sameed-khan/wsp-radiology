import hashlib
import json
import os
import stat

import pytest

from wsp_arms import arm_d_labels, core


@pytest.fixture
def fake_pi(tmp_path, monkeypatch):
    root = tmp_path / 'root'
    (root / 'config').mkdir(parents=True)
    (root / 'config/arm-d-prompt.md').write_text('prompt')
    (root / 'data/pool').mkdir(parents=True)
    (root / 'data/pool/image.png').write_bytes(b'image')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    script = bin_dir / 'pi'
    script.write_text('''#!/usr/bin/env python3
import os, pathlib, sys, time
state = pathlib.Path(os.environ['FAKE_STATE'])
n = int(state.read_text()) if state.exists() else 0
state.write_text(str(n + 1))
mode = os.environ['FAKE_MODE']
if mode == 'timeout': time.sleep(2)
if mode == 'exit' or (mode == 'recover' and n < 2):
    print('failure', file=sys.stderr); sys.exit(1)
if mode == '429': print('HTTP 429 Too Many Requests'); sys.exit(0)
if mode == 'usage': print('Usage limit reached', file=sys.stderr); sys.exit(0)
if mode == 'invalid': print('not json'); sys.exit(0)
print('{"p_monteggia": 42}')
''')
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    state = tmp_path / 'state'
    monkeypatch.setenv('FAKE_STATE', str(state))
    monkeypatch.setenv('PATH', str(bin_dir) + os.pathsep + os.environ['PATH'])
    monkeypatch.setattr(arm_d_labels, 'INFRA_RETRY_SECONDS', 0.3)
    monkeypatch.setattr(arm_d_labels.time, 'sleep', lambda _: None)
    return root, state


def run(root, **kwargs):
    return arm_d_labels.run(root, workers=1, timeout=.05, **kwargs)


def test_infrastructure_retries_then_succeeds(fake_pi, monkeypatch):
    root, state = fake_pi
    monkeypatch.setenv('FAKE_MODE', 'recover')
    result = run(root)
    assert result['failed'] == 0
    row = json.loads((root / 'data/locked/private/arm-d/labels.jsonl').read_text())
    assert row['p_monteggia'] == 42 and row['attempts'] == 3
    assert state.read_text() == '3'
    assert run(root)['new'] == 0


@pytest.mark.parametrize('mode', ['exit', 'timeout', '429', 'usage'])
def test_infrastructure_never_cached_and_rerun(fake_pi, monkeypatch, mode):
    root, state = fake_pi
    monkeypatch.setenv('FAKE_MODE', mode)
    result = run(root)
    cache = root / 'data/locked/private/arm-d/labels.jsonl'
    assert result['uncached'] == 1 and result['failed'] == 1
    assert not cache.read_text()
    monkeypatch.setenv('FAKE_MODE', 'success')
    assert run(root)['failed'] == 0
    assert json.loads(cache.read_text())['p_monteggia'] == 42


def test_validation_failure_cached_after_three(fake_pi, monkeypatch):
    root, state = fake_pi
    monkeypatch.setenv('FAKE_MODE', 'invalid')
    result = run(root)
    row = json.loads((root / 'data/locked/private/arm-d/labels.jsonl').read_text())
    assert result['excluded'] == 1 and row['attempts'] == 3
    assert state.read_text() == '3'
    assert run(root)['new'] == 0


def test_old_infrastructure_exclusion_is_removed(fake_pi, monkeypatch):
    root, _ = fake_pi
    directory = root / 'data/locked/private/arm-d'
    directory.mkdir(parents=True)
    image = root / 'data/pool/image.png'
    row = dict(image=image.name, image_sha256=core.sha256_file(image),
               prompt_sha256=hashlib.sha256(b'prompt').hexdigest(), model=arm_d_labels.MODEL,
               p_monteggia=None, error='CalledProcessError')
    cache = directory / 'labels.jsonl'
    cache.write_text(json.dumps(row) + '\n')
    monkeypatch.setenv('FAKE_MODE', 'success')
    assert run(root)['failed'] == 0
    rows = [json.loads(line) for line in cache.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]['p_monteggia'] == 42
