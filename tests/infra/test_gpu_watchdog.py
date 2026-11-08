import json
import subprocess

from infra import gpu_watchdog as watchdog


def test_poll_kills_only_largest_process_in_over_cap_container(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(watchdog, "_processes", lambda: [(101, 700), (102, 500), (103, 2000)])
    monkeypatch.setattr(watchdog, "_container_pid", lambda pid, cid: {101: 1, 102: 2}.get(pid))
    monkeypatch.setattr(watchdog, "_run", lambda *args: calls.append(args))
    log = tmp_path / "gpu.jsonl"
    watchdog.poll({"wsp-run": ("a" * 64, 1)}, log, True)
    assert calls == [("docker", "exec", "-u", "0", "wsp-run", "kill", "-9", "1")]
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["event"] for e in events] == ["sample", "violation"]
    assert events[0]["memory_mib"] == 1200


def test_poll_handles_process_disappearing_before_kill(monkeypatch, tmp_path):
    monkeypatch.setattr(watchdog, "_processes", lambda: [(101, 1200)])
    results = iter([1, None])
    monkeypatch.setattr(watchdog, "_container_pid", lambda *args: next(results))
    monkeypatch.setattr(watchdog, "_run", lambda *args: (_ for _ in ()).throw(AssertionError()))
    watchdog.poll({"wsp-run": ("a" * 64, 1)}, tmp_path / "log", False)


def test_poll_records_kill_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(watchdog, "_processes", lambda: [(101, 1200)])
    monkeypatch.setattr(watchdog, "_container_pid", lambda *args: 1)
    def fail(*args):
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(watchdog, "_run", fail)
    log = tmp_path / "log"
    watchdog.poll({"wsp-run": ("a" * 64, 1)}, log, False)
    assert json.loads(log.read_text())["event"] == "kill-failed"
