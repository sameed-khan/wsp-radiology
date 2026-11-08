import json
import os
import subprocess
import time
import uuid

import pytest

from wsp_harness.evidence import snapshot, verify_events


def lines(path, records):
    path.write_text(''.join(json.dumps(record) + '\n' for record in records))


def test_snapshots_link_dest_and_manifest(tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    (workspace / 'small').write_text('hello')
    (workspace / 'model.pt').write_bytes(b'x' * (1024 * 1024 + 1))
    (workspace / 'link').symlink_to('/not/followed')
    first = snapshot(workspace, tmp_path / 'snapshots')
    second = snapshot(workspace, tmp_path / 'snapshots')
    assert os.stat(first / 'workspace/small').st_ino == os.stat(second / 'workspace/small').st_ino
    manifest = json.loads((second / 'manifest.json').read_text())
    assert next(x for x in manifest if x['path'] == 'link')['target'] == '/not/followed'
    assert [x['path'] for x in json.loads((second / 'checkpoints.json').read_text())] == ['model.pt']
    (workspace / 'small').write_text('world')
    third = snapshot(workspace, tmp_path / 'snapshots')
    assert (first / 'workspace/small').read_text() == 'hello'
    assert (third / 'workspace/small').read_text() == 'world'
    with pytest.raises(ValueError):
        snapshot(workspace, workspace / 'nested')


def test_completeness_is_bidirectional_and_counts_duplicates(tmp_path):
    events, session = tmp_path / 'events', tmp_path / 'session'
    event = {'type': 'tool_execution_end', 'toolCallId': 'id', 'toolName': 'bash'}
    result = {'type': 'message', 'message': {'role': 'toolResult', 'toolCallId': 'id', 'toolName': 'bash'}}
    lines(events, [event]); lines(session, [result])
    assert verify_events(events, [session])['complete']
    lines(events, [event, event]); assert verify_events(events, [session])['missing_results'][0]['count'] == 1
    lines(events, []); assert verify_events(events, [session])['missing_events'][0]['count'] == 1
    with pytest.raises(ValueError):
        verify_events(events, [])
    events.write_text('{')
    with pytest.raises(ValueError):
        verify_events(events, [session])


@pytest.mark.skipif(os.environ.get('WSP_LIVE_SNAPSHOT_TEST') != '1', reason='requires Docker')
def test_paused_container_snapshot(tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir(mode=0o777)
    workspace.chmod(0o777)
    # Docker's non-root UID must be able to traverse pytest's temp parents.
    for path in [tmp_path, tmp_path.parent, tmp_path.parent.parent]:
        path.chmod(0o755)
    name = 'wsp-snapshot-' + uuid.uuid4().hex[:12]
    try:
        subprocess.run(['docker', 'run', '-d', '--name', name, '--network', 'none',
                        '--user', '1004:1004', '--cap-drop', 'ALL', '--security-opt',
                        'no-new-privileges', '--read-only', '--tmpfs', '/tmp',
                        '-v', f'{workspace}:/workspace', 'ubuntu:24.04', 'sh', '-c',
                        'while :; do date +%s%N > /workspace/tick; sleep .1; done'],
                       check=True, capture_output=True)
        for _ in range(100):
            if (workspace / 'tick').exists():
                break
            time.sleep(.05)
        assert (workspace / 'tick').exists()
        subprocess.run(['docker', 'pause', name], check=True, capture_output=True)
        frozen = (workspace / 'tick').read_bytes()
        snap = snapshot(workspace, tmp_path / 'snapshots')
        time.sleep(.3)
        assert (workspace / 'tick').read_bytes() == frozen
        assert (snap / 'workspace/tick').read_bytes() == frozen
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
