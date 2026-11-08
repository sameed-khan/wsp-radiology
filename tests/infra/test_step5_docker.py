"""Step 5 live tests: workspace watcher and GPU watchdog against a real hardened sandbox (GPU, Docker)."""
import io
import json
import os
import signal
import subprocess
import sys
import time
import uuid
import zipfile

import pytest

from infra import gpu_watchdog as gw
from infra import sandbox as sbx
from infra import watcher as W
from tests.infra.test_watcher import NAMES, POOL_IM, POOL_JPG, TEST_IM, TEST_JPG, enc, make_image, ph, sha

pytestmark = pytest.mark.docker
AGENT_IMAGE = "wsp-agent-base:step1"
CAP_GIB = 0.05  # 51 MiB: any CUDA context exceeds it


def ex(sb, *cmd, **kw):
    return subprocess.run(sbx.exec_argv(sb, list(cmd), **kw), text=True, capture_output=True)


def events(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    t = tmp_path_factory.mktemp("s5")
    for d in ("ws", "pool", "labels", "models", "external"):
        (t / d).mkdir()
    (t / "ws").chmod(0o777)
    (t / "labels/labels.csv").write_text("a,b\n")
    corpus = {"archive_sha256": "c" * 64, "raw_sha256": [sha(TEST_JPG), sha(POOL_JPG)], "normalized_sha256": [],
              "phash": {"pool": [ph(POOL_IM)], "test": [ph(TEST_IM)]}, "basenames": NAMES}
    (t / "corpus.json").write_text(json.dumps(corpus))
    run = "s5" + uuid.uuid4().hex[:8]
    spec = sbx.SandboxSpec(run, t / "ws", t / "pool", t / "labels", t / "models", t / "external", AGENT_IMAGE,
                           t / "state", t / "corpus.json", gpu_mem_cap_gib=CAP_GIB, cpus=2, memory="8g")
    sb = sbx.create(spec)
    try:
        yield t, spec, sb
    finally:
        sbx.destroy(sb)


def stage(t, name, data):
    """Host drops bytes into a non-scanned spot; the agent (uid 1004 in the container) copies them in."""
    src = t / "ws" / ".stage"
    src.mkdir(exist_ok=True)
    (src / "f").write_bytes(data)
    return src / "f"


def agent_write(sb, t, rel, data):
    stage(t, rel, data)
    r = ex(sb, "sh", "-c", f"mkdir -p \"$(dirname /workspace/{rel})\" && cp /workspace/.stage/f /workspace/{rel}")
    assert r.returncode == 0, r.stderr
    (t / "ws" / ".stage" / "f").unlink()


def test_watcher_against_real_sandbox_workspace(env):
    t, spec, sb = env
    ctl = spec.state_dir / "control"
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("m/t.jpg", TEST_JPG)
    agent_write(sb, t, "clean/ok.jpg", enc(make_image(1234)))
    agent_write(sb, t, "out/pool_small.jpg", enc(POOL_IM.resize((150, 110)), quality=50))
    agent_write(sb, t, "out/notes.txt", b"just notes")
    argv = [sys.executable, "-m", "infra.watcher", "--workspace", str(spec.workspace), "--corpus", str(spec.hash_corpus),
            "--state-dir", str(spec.state_dir / "watcher"), "--control-dir", str(ctl), "--interval", "3600",
            "--run-id", spec.run_id]
    proc = subprocess.Popen(argv)
    log = spec.state_dir / "watcher" / "watcher.jsonl"
    try:
        def wait(pred, timeout=60):
            end = time.time() + timeout
            while time.time() < end:
                if pred():
                    return True
                time.sleep(0.5)
            return False

        assert wait(lambda: any(e.get("event") == "scan" for e in events(log)))
        f1 = {e["file"]: (e["level"], e["rule"]) for e in events(log) if e.get("event") == "finding"}
        assert f1 == {"out/pool_small.jpg": ("info", "pool-derivative")}, f1
        assert not (ctl / W.STOP_FILE).exists()  # non-exact pool derivatives do not stop the run
        # agent now writes a test-split derivative inside an archive; on-demand scan via SIGUSR1
        agent_write(sb, t, "out/results.zip", z.getvalue())
        proc.send_signal(signal.SIGUSR1)
        assert wait((ctl / W.STOP_FILE).exists)
        req = json.loads((ctl / W.STOP_FILE).read_text())
        assert req["file"] == "out/results.zip" and req["rule"] in ("phash-test", "sha256") and req["reason"] and req["time"]
        # the control dir and watcher log are host-only: not visible in the container
        assert ex(sb, "sh", "-c", f"ls {ctl} {spec.state_dir} 2>&1").returncode != 0
        text = log.read_text()
        for secret in (sha(TEST_JPG), ph(TEST_IM), *NAMES):
            assert secret not in text
    finally:
        proc.kill()
        proc.wait()


TORCH_ALLOC = ("import torch,time; x=torch.ones(64*1024*1024,device='cuda'); "
               "print('ready',flush=True); "
               "exec('while True:\\n  x=x*1.0001\\n  torch.cuda.synchronize()')")


def start_gpu_proc(sb):
    p = subprocess.Popen(sbx.exec_argv(sb, ["python3", "-c", TORCH_ALLOC]), stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "ready"
    return p


def test_pid_mapping_and_samples_against_live_container(env):
    t, spec, sb = env
    cid = gw._run("docker", "inspect", "--format", "{{.Id}}", sb.container).strip()
    p = start_gpu_proc(sb)
    try:
        host = [(pid, mem) for pid, mem in gw._processes() if gw._container_pid(pid, cid) is not None]
        assert len(host) == 1 and host[0][1] > 50
        pid = host[0][0]
        nspid = gw._container_pid(pid, cid)
        assert nspid != 1  # agent work is never PID 1 (tini is)
        assert gw._process_uid(pid) == 1004
        ps = ex(sb, "ps", "-o", "pid=,args=", "-p", str(nspid)).stdout
        assert "torch" in ps  # the mapped namespace pid really is our process
        assert ex(sb, "ps", "-o", "args=", "-p", "1").stdout.strip().startswith("/usr/bin/tini")
        # no other container's processes map to this one
        assert gw._container_pid(pid, "0" * 64) is None
        log = t / "samples.jsonl"
        for _ in range(3):  # pmon utilization of a spinning kernel loop
            gw.poll({sb.container: (cid, 1000.0)}, log, True)
            time.sleep(1)
        samples = [e for e in events(log) if e["event"] == "sample"]
        assert samples and samples[0]["memory_mib"] > 50
        assert all(e["event"] in ("sample", "utilization-unavailable") for e in events(log))  # no violation at 1000 GiB
        utils = [s["sm_utilization_percent"] for s in samples]
        print("sm utilization samples:", utils)
        assert any(u is not None and u > 0 for u in utils) or any(
            e["event"] == "utilization-unavailable" for e in events(log)), utils
    finally:
        p.kill()
        ex(sb, "pkill", "-9", "-f", "torch")


def test_watchdog_kills_over_cap_process_in_sandbox(env):
    t, spec, sb = env
    state = spec.state_dir / "gpu"
    wd = subprocess.Popen([sys.executable, "-m", "infra.gpu_watchdog", "--state-dir", str(state),
                           "--sandbox-json", str(spec.state_dir / "sandbox.json")])
    p = start_gpu_proc(sb)
    try:
        log = state / "gpu-watchdog.jsonl"
        end = time.time() + 60
        while time.time() < end and not any(e["event"] in ("violation", "kill-failed") for e in events(log)):
            time.sleep(1)
        ev = events(log)
        v = [e for e in ev if e["event"] == "violation"]
        assert v, ev
        assert v[0]["container"] == sb.container and v[0]["memory_mib"] > CAP_GIB * 1024 and v[0]["cap_gib"] == CAP_GIB
        assert p.wait(timeout=30) != 0  # killed (SIGKILL of the exec'd torch process)
        # offending process gone; sandbox itself survives and is usable
        assert subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", sb.container],
                              capture_output=True, text=True).stdout.strip() == "true"
        assert ex(sb, "pgrep", "-f", "torch").returncode != 0
        assert ex(sb, "echo", "alive").stdout.strip() == "alive"
        assert any(e["event"] == "sample" for e in ev)
    finally:
        wd.kill()
        wd.wait()
        p.kill()
        ex(sb, "pkill", "-9", "-f", "torch")
