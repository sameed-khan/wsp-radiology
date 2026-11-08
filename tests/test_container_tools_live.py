"""Opt-in paid integration test: WSP_LIVE_CONTAINER_TEST=1 uv run pytest -q tests/test_container_tools_live.py.

Requires Docker, cached ubuntu:24.04, and host Pi Haiku credentials. Creates only
its own disposable wsp-* container and never mounts host Pi configuration.
"""
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from PIL import Image

pytestmark = pytest.mark.skipif(os.environ.get("WSP_LIVE_CONTAINER_TEST") != "1", reason="paid Docker/Pi integration test")


def test_container_tools(tmp_path):
    # Docker's configured numeric user must be able to traverse pytest's dirs.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="wsp-tools-", dir="/tmp") as work:
        root = Path(work)
        root.chmod(0o777)
        Image.new("RGB", (32, 32), (255, 0, 0)).save(root / "image.png")
        name = "wsp-tools-" + uuid.uuid4().hex[:12]
        subprocess.run(["docker", "run", "-d", "--name", name, "--hostname", name,
                        "--network", "none", "--user", "1004:1004", "--cap-drop", "ALL",
                        "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:rw,nosuid",
                        "--mount", f"type=bind,src={root},dst=/workspace", "-w", "/workspace",
                        "ubuntu:24.04", "sleep", "infinity"], check=True, capture_output=True)
        try:
            env = os.environ | {"WSP_CONTAINER": name, "WSP_EXEC_USER": "1004:1004"}
            prompt = ("Use bash to run hostname and test -e /home/skhanxx8/projects/wsp-radiology/plan.md; "
                      "write result.txt containing hello; use edit to change hello to goodbye; "
                      "use read on image.png. Then use bash with timeout 1 to run "
                      "'sleep 4; echo survived > /workspace/should-not-exist'. Do not retry the timed-out command.")
            p = subprocess.run(["pi", "--mode", "json", "-p", "--no-session", "--model", "anthropic/claude-haiku-5-5",
                                "--no-extensions", "-e", "harness/pi-ext/container-tools.ts", "--no-skills",
                                "--no-context-files", "--no-prompt-templates", "--tools", "read,write,edit,bash", prompt],
                               env=env, text=True, capture_output=True, check=True, timeout=150)
            events = [json.loads(line) for line in p.stdout.splitlines()]
            ends = [e for e in events if e.get("type") == "tool_execution_end"]
            assert {"read", "write", "edit", "bash"} <= {e["toolName"] for e in ends}
            assert any(any(c.get("type") == "image" for c in e["result"]["content"]) for e in ends if e["toolName"] == "read")
            assert any(name in str(e["result"]) for e in ends if e["toolName"] == "bash")
            assert any(e.get("isError") and "timed out" in str(e["result"]).lower() for e in ends if e["toolName"] == "bash")
            assert (root / "result.txt").read_text() == "goodbye"
            time.sleep(5)
            assert not (root / "should-not-exist").exists()
            check = subprocess.run(["docker", "exec", name, "test", "-e", "/home/skhanxx8/projects/wsp-radiology/plan.md"])
            assert check.returncode != 0
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=True)
