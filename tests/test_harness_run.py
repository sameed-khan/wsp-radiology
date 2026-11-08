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


def test_create_run(tmp_path):
    labels, pool = inputs(tmp_path)
    run = create_run(tmp_path, 'F', 10, labels, pool, 0.05, test_model=True)
    launch = json.loads((run / 'launch.json').read_text())
    assert run.stat().st_mode & 0o777 == 0o700
    assert launch['model'] == 'anthropic/claude-haiku-5-5'
    assert launch['image_id'].startswith('sha256:')
    assert (run / 'workspace/TASK.md').read_text() == launch['launch_prompt']


@pytest.mark.skipif(os.environ.get('WSP_LIVE') != '1', reason='paid live Haiku test')
def test_live_run(tmp_path):
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
