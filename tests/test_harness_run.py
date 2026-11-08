"""Unit A: opt-in paid Docker/Haiku integration test."""
import json
import os
from pathlib import Path
import shutil

import pytest

from wsp_harness.config import load_inputs
from wsp_harness.run import RpcDriver, create_run
from wsp_harness import sandbox_simple

FIXTURE = Path(__file__).parent / 'fixtures/harness'


def inputs(tmp_path):
    shutil.copytree(FIXTURE / '.pi', tmp_path / '.pi')
    (tmp_path / '.pi/prompts/wsp-launch.md').write_text(
        'Use bash to run `hostname`, then use the write tool to write /workspace/output/x.txt containing hello, then stop.')
    labels = tmp_path / 'labels'
    pool = tmp_path / 'pool'
    labels.mkdir()
    pool.mkdir()
    (labels / 'labels.csv').write_text('image,patient,label\n')
    return labels, pool


def test_create_run(tmp_path, sae_fixture):
    labels, pool = inputs(tmp_path)
    run = create_run(tmp_path, 'F', 10, labels, pool, 0.05, test_model=True)
    launch = json.loads((run / 'launch.json').read_text())
    assert run.stat().st_mode & 0o777 == 0o700
    assert launch['model'] == 'anthropic/claude-haiku-5-5'
    assert launch['image_id'].startswith('sha256:')
    assert (run / 'workspace/TASK.md').read_text() == launch['launch_prompt']
    from wsp_harness.sae import validate_package
    dest = run / 'workspace/provided/sae'
    assert launch['sae_manifest_sha256'] == validate_package(dest)
    assert dest.stat().st_mode & 0o777 == 0o555
    assert all(p.stat().st_mode & 0o777 == 0o444 for p in dest.iterdir())
    shutil.copyfile(tmp_path / '.pi/agents/wsp-arm-f.md', tmp_path / '.pi/agents/wsp-arm-g.md')
    other = create_run(tmp_path, 'G', 10, labels, pool, 0.05, test_model=True)
    assert json.loads((other / 'launch.json').read_text())['sae_manifest_sha256'] == launch['sae_manifest_sha256']
    from wsp_harness.run import REPO
    for directory in ('agents', 'prompts'):
        shutil.copyfile(REPO / f'.pi/{directory}/wsp-redteam.md', tmp_path / f'.pi/{directory}/wsp-redteam.md')
    red = create_run(tmp_path, 'R', 0, labels, pool, 0.05, test_model=True)
    assert json.loads((red / 'launch.json').read_text())['sae_manifest_sha256'] == launch['sae_manifest_sha256']


def test_missing_and_corrupt_sae(tmp_path, sae_fixture):
    labels, pool = inputs(tmp_path)
    (sae_fixture / 'README.md').write_text('tampered')
    with pytest.raises(ValueError, match='hash mismatch'):
        create_run(tmp_path, 'G', 10, labels, pool, 1, test_model=True)
    shutil.rmtree(sae_fixture)
    with pytest.raises(ValueError, match='missing'):
        create_run(tmp_path, 'F', 10, labels, pool, 1, test_model=True)
    from wsp_harness.run import REPO
    for directory in ('agents', 'prompts'):
        shutil.copyfile(REPO / f'.pi/{directory}/wsp-redteam.md', tmp_path / f'.pi/{directory}/wsp-redteam.md')
    run = create_run(tmp_path, 'R', 0, labels, pool, 1, test_model=True)
    assert json.loads((run / 'launch.json').read_text())['sae_manifest_sha256'] is None
    assert not (run / 'workspace/provided/sae').exists()


@pytest.mark.skipif(os.environ.get('WSP_LIVE') != '1', reason='paid live Haiku test')
def test_live_run(tmp_path, sae_fixture):
    labels, pool = inputs(tmp_path)
    run = create_run(tmp_path, 'F', 10, labels, pool, 0.05, test_model=True)
    container = sandbox_simple.create(run)
    driver = None
    try:
        driver = RpcDriver(run, load_inputs(tmp_path, 'F', allow_test_model=True), container)
        driver.prompt(json.loads((run / 'launch.json').read_text())['launch_prompt'])
        driver.wait_idle(150)
        assert (run / 'workspace/output/x.txt').read_text().strip() == 'hello'
        events = [json.loads(line) for line in (run / 'recorder/rpc-events.jsonl').read_text().splitlines()]
        assert {'bash', 'write'} <= {e.get('toolName') for e in events if e.get('type') == 'tool_execution_end'}
        bash = [e for e in events if e.get('type') == 'tool_execution_end' and e.get('toolName') == 'bash']
        assert container in json.dumps(bash)  # hostname ran inside the sandbox, not on the host
        assert events[-1]['type'] == 'agent_settled'
        recv = (run / 'recorder/rpc-receive-times.jsonl').read_text().splitlines()
        assert len(recv) == len(events)
        assert list((run / 'recorder/sessions').glob('*.jsonl'))
    finally:
        if driver:
            driver.close()
        sandbox_simple.destroy(container)
