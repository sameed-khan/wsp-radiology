import json
from pathlib import Path

from wsp_harness import sandbox_infra


def test_dead_helpers_are_restarted_and_logged(tmp_path, monkeypatch):
    state = tmp_path / 'state'
    state.mkdir()
    (state / 'backend.json').write_text(json.dumps({'hash_corpus': '/corpus'}))

    class Proc:
        def __init__(self, name, code):
            self.args = ['python', '-m', name]
            self.returncode = code
        def poll(self):
            return self.returncode

    watcher = Proc('infra.watcher', 1)
    gpu = Proc('infra.gpu_watchdog', 2)
    monkeypatch.setattr(sandbox_infra, '_HELPERS', [watcher, gpu])
    def spawn(run, argv, env=None):
        sandbox_infra._HELPERS.append(Proc(argv[2], None))
    monkeypatch.setattr(sandbox_infra, '_spawn_helper', spawn)
    messages = []
    sandbox_infra.check_helpers(tmp_path, 'wsp-agent-test', messages.append)
    assert len(messages) == 2 and all('restarting' in m for m in messages)
    assert [p.args[2] for p in sandbox_infra._HELPERS] == ['infra.watcher', 'infra.gpu_watchdog']
    sandbox_infra.check_helpers(tmp_path, 'wsp-agent-test', messages.append)
    assert len(messages) == 2
