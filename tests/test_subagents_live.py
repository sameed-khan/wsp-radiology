"""Opt-in paid Docker/Haiku test: WSP_LIVE_SUBAGENT_TEST=1 uv run pytest -q tests/test_subagents_live.py."""
import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("WSP_LIVE_SUBAGENT_TEST") != "1", reason="paid Docker/Pi integration test")


def test_children(tmp_path):
    with tempfile.TemporaryDirectory(prefix="wsp-subagents-", dir="/tmp") as workspace:
        Path(workspace).chmod(0o777)
        name = "wsp-subagents-" + uuid.uuid4().hex[:12]
        subprocess.run(["docker", "run", "-d", "--name", name, "--network", "none", "--user", "1004:1004", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:rw,nosuid", "--mount", f"type=bind,src={workspace},dst=/workspace", "-w", "/workspace", "ubuntu:24.04", "sleep", "infinity"], check=True, capture_output=True)
        try:
            env = os.environ | {"WSP_CONTAINER": name, "WSP_EXEC_USER": "1004:1004", "WSP_RECORDER_DIR": str(tmp_path), "WSP_DEADLINE_EPOCH": str(time.time() + 180)}
            prompt = ("Call subagent twice: first wait=true task='Use bash to run hostname and report it; use Opus if possible', "
                      "second wait=false task='Use write to create /workspace/child.txt containing async-ok; report done'. "
                      "Then call subagent_result with the second id and wait=true. Report both results.")
            p = subprocess.run(["pi", "--mode", "json", "-p", "--no-session", "--model", "anthropic/claude-haiku-5-5", "--no-extensions", "-e", "harness/pi-ext/container-tools.ts", "-e", "harness/pi-ext/subagents.ts", "--no-skills", "--no-context-files", "--no-prompt-templates", "--no-mcp", "--tools", "read,write,edit,bash,subagent,subagent_result", prompt], env=env, text=True, capture_output=True, timeout=180, check=True)
            events = [json.loads(x) for x in p.stdout.splitlines()]
            starts = [e for e in events if e.get("type") == "tool_execution_start"]
            calls = [e for e in starts if e.get("toolName") == "subagent"]
            assert len(calls) == 2, p.stdout[-10000:]
            assert {c["args"].get("wait", True) for c in calls} == {True, False}
            assert any(e.get("toolName") == "subagent_result" and e["args"].get("wait") for e in starts)
            assert (Path(workspace) / "child.txt").read_text().strip() == "async-ok"
            child_dir = tmp_path / "subagents"
            sessions = [p for p in child_dir.glob("*.jsonl") if not p.name.endswith(".events.jsonl")]
            assert len(sessions) == 2, list(child_dir.iterdir())
            for session in sessions:
                messages = [e["message"] for e in map(json.loads, session.read_text().splitlines()) if e.get("type") == "message" and e["message"].get("role") == "assistant"]
                assert messages and all(m["model"] == "claude-haiku-5-5" and m["provider"] == "anthropic" for m in messages)
                assert not any(c.get("name") == "subagent" for m in messages for c in m.get("content", []))
            assert len(list(child_dir.glob("*.events.jsonl"))) == 2
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=True)
