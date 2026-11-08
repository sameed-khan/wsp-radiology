import json
import subprocess

import pytest

from infra import gpu_watchdog as watchdog


def test_poll_kills_only_largest_process_in_over_cap_container(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(watchdog, "_processes", lambda: [(101, 700), (102, 500), (103, 2000)])
    monkeypatch.setattr(watchdog, "_utilization", lambda: {101: 20, 102: 30})
    monkeypatch.setattr(watchdog, "_container_pid", lambda pid, cid: {101: 3, 102: 2}.get(pid))
    monkeypatch.setattr(watchdog, "_process_uid", lambda pid: 1004)
    monkeypatch.setattr(watchdog, "_run", lambda *args: calls.append(args))
    log = tmp_path / "gpu.jsonl"
    watchdog.poll({"wsp-run": ("a" * 64, 1)}, log, True)
    assert calls == [("docker", "exec", "-u", "1004", "wsp-run", "kill", "-9", "3")]
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["event"] for e in events] == ["sample", "violation"]
    assert events[0]["memory_mib"] == 1200
    assert events[0]["sm_utilization_percent"] == 50


def test_utilization_parses_pmon(monkeypatch):
    monkeypatch.setattr(watchdog, "_run", lambda *args: "# header\n0 101 C 20 0 0 0 - - cmd\n0 102 C - - - - - - cmd\n")
    assert watchdog._utilization() == {101: 20}


def test_unavailable_utilization_does_not_prevent_enforcement(monkeypatch, tmp_path):
    monkeypatch.setattr(watchdog, "_processes", lambda: [(101, 1200)])
    monkeypatch.setattr(watchdog, "_container_pid", lambda *args: 3)
    monkeypatch.setattr(watchdog, "_utilization", lambda: (_ for _ in ()).throw(OSError()))
    calls = []
    monkeypatch.setattr(watchdog, "_run", lambda *args: calls.append(args))
    log = tmp_path / "log"
    watchdog.poll({"wsp-run": ("a" * 64, 1)}, log, True)
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [event["event"] for event in events] == ["utilization-unavailable", "sample", "violation"]
    assert events[1]["sm_utilization_percent"] is None
    assert calls


def test_poll_handles_process_disappearing_before_kill(monkeypatch, tmp_path):
    monkeypatch.setattr(watchdog, "_processes", lambda: [(101, 1200)])
    results = iter([1, None])
    monkeypatch.setattr(watchdog, "_container_pid", lambda *args: next(results))
    monkeypatch.setattr(watchdog, "_run", lambda *args: (_ for _ in ()).throw(AssertionError()))
    watchdog.poll({"wsp-run": ("a" * 64, 1)}, tmp_path / "log", False)


def test_pid_namespace_init_is_not_falsely_reported_killed(monkeypatch, tmp_path):
    monkeypatch.setattr(watchdog, "_processes", lambda: [(101, 1200)])
    monkeypatch.setattr(watchdog, "_container_pid", lambda *args: 1)
    monkeypatch.setattr(watchdog, "_run", lambda *args: pytest.fail("must not signal namespace init"))
    log = tmp_path / "log"
    watchdog.poll({"wsp-run": ("a" * 64, 1)}, log, False)
    event = json.loads(log.read_text())
    assert event["event"] == "kill-failed"
    assert event["reason"] == "namespace-init"


def test_poll_records_kill_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(watchdog, "_processes", lambda: [(101, 1200)])
    monkeypatch.setattr(watchdog, "_container_pid", lambda *args: 3)
    def fail(*args):
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(watchdog, "_run", fail)
    log = tmp_path / "log"
    watchdog.poll({"wsp-run": ("a" * 64, 1)}, log, False)
    assert json.loads(log.read_text())["event"] == "kill-failed"
