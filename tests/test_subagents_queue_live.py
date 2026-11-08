"""Paid parent Pi test with fake child executables for queue/deadline edge cases."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("WSP_LIVE_SUBAGENT_TEST") != "1", reason="paid Pi integration test")


def test_queue_deadline_and_model_rejection(tmp_path):
    parent_pi = shutil.which("pi")
    fake = tmp_path / "pi"
    fake.write_text("#!/bin/sh\nprintf 'started\\n' >> \"$WSP_FAKE_STARTS\"\nexec sleep 30\n")
    fake.chmod(0o755)
    env = os.environ | {"PATH": str(tmp_path) + ":" + os.environ["PATH"], "WSP_CONTAINER": "wsp-unused", "WSP_EXEC_USER": "1004:1004", "WSP_RECORDER_DIR": str(tmp_path / "recorder"), "WSP_DEADLINE_EPOCH": str(time.time() + 12), "WSP_FAKE_STARTS": str(tmp_path / "starts")}
    p = subprocess.run([parent_pi, "--mode", "json", "-p", "--no-session", "--model", "anthropic/claude-haiku-5-5", "--no-extensions", "-e", "harness/pi-ext/subagents.ts", "-e", "tests/subagent-driver.ts", "--no-skills", "--no-context-files", "--no-prompt-templates", "--no-mcp", "--tools", "exercise_subagents,subagent,subagent_result", "Call exercise_subagents now, once."], env=env, text=True, capture_output=True, timeout=50, check=True)
    events = [json.loads(line) for line in p.stdout.splitlines()]
    end = next(e for e in events if e.get("type") == "tool_execution_end" and e.get("toolName") == "exercise_subagents")
    assert not end.get("isError"), end
    data = json.loads(end["result"]["content"][0]["text"])
    assert data["invalid"]["isError"]
    statuses = [json.loads(x["result"]["content"][0]["text"])["status"] for x in data["results"]]
    assert statuses == ["failed"] * 9
    assert len((tmp_path / "starts").read_text().splitlines()) == 8
