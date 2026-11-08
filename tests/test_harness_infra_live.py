"""Paid real-topology integration; uses no locked labels or test images."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest

ROOT = Path('/home/skhanxx8/projects/wsp-radiology')
FIXTURE = Path(__file__).parent / 'fixtures/harness/.pi'


@pytest.mark.skipif(os.environ.get('WSP_LIVE') != '1', reason='paid live infra test')
def test_infra_launch_deadline(tmp_path, sae_fixture):
    shutil.copytree(FIXTURE, tmp_path / '.pi')
    (tmp_path / '.pi/prompts/wsp-launch.md').write_text(
        'Use bash to run exactly: nvidia-smi; python -c "import torch;print(torch.cuda.is_available())"; '
        'curl -sI https://pypi.org/simple/; curl -s -o /dev/null -w "%{http_code}" '
        'https://figshare.com/articles/dataset/x/30335941; ls -d /inputs/* . '
        'Then use subagent wait=true to run echo CHILD_OK and report it. '
        'Do not create FINAL; stop after reporting results.')
    labels = tmp_path / 'labels'; labels.mkdir()
    (labels / 'labels.csv').write_text('image,patient,label\n')
    def cli(*args):
        return subprocess.run([sys.executable, '-m', 'wsp_harness.cli', '--root', str(tmp_path), *args],
                              text=True, capture_output=True, timeout=120)
    launch = cli('launch', '--arm', 'F', '--k', '10', '--labels', str(labels), '--pool', str(ROOT / 'data/pool'),
                 '--backend', 'infra', '--models-dir', str(ROOT / 'models'), '--external-dir',
                 str(ROOT / 'data/external/extracted'),
                 '--hash-corpus', str(ROOT / 'data/locked/private/hash-corpus.json'), '--hours', str(4/60), '--test-model')
    assert launch.returncode == 0, launch.stderr
    run = tmp_path / 'runs' / launch.stdout.strip().splitlines()[-1]
    try:
        # Exercise actual helper supervision, not only mocked process polling.
        deadline = time.time() + 30
        while time.time() < deadline:
            ps = subprocess.check_output(['ps', '-eo', 'pid=,args='], text=True).splitlines()
            helpers = [line.strip().split(None, 1) for line in ps
                       if str(run / 'state') in line and ('-m infra.watcher' in line or '-m infra.gpu_watchdog' in line)]
            if len(helpers) == 2:
                break
            time.sleep(0.5)
        assert len(helpers) == 2
        for pid, _ in helpers:
            os.kill(int(pid), signal.SIGKILL)
        end = time.time() + 310
        while time.time() < end:
            status_path = run / 'state/status.json'
            status = json.loads(status_path.read_text()) if status_path.exists() else {}
            if str(status.get('phase', '')).startswith('frozen'):
                break
            time.sleep(2)
        assert status.get('phase') == 'frozen', status
        assert status['reason'] == 'deadline', status
        events = (run / 'recorder/rpc-events.jsonl').read_text()
        assert 'CHILD_OK' in events and '403' in events and 'True' in events
        assert 'pypi.org' in events and '/inputs/models' in events and 'NVIDIA' in events
        verify = cli('verify', '--run', run.name)
        assert verify.returncode == 0, verify.stdout + verify.stderr
        assert json.loads(verify.stdout)['subagents']
        account = cli('account', '--run', run.name, '--no-prices')
        assert account.returncode == 0 and json.loads(account.stdout)['total']['messages'] > 0
        assert list((run / 'state/proxy').glob('*.jsonl'))
        assert (run / 'state/watcher.log').exists() and (run / 'state/gpu_watchdog.log').exists()
        supervisor_log = (run / 'recorder/supervisor.log').read_text()
        assert 'helper infra.watcher exited' in supervisor_log
        assert 'helper infra.gpu_watchdog exited' in supervisor_log
        for kind in ('container', 'network'):
            result = subprocess.check_output(['docker', kind, 'ls', *(['-a'] if kind == 'container' else []), '--filter', f'label=wsp.run={run.name}', '--format', '{{.ID}}'], text=True)
            assert not result.strip()
    finally:
        if not str(status.get('phase', '')).startswith('frozen'):
            cli('stop', '--run', run.name, '--reason', 'test cleanup')
