"""Step 4: real sandbox lifecycle via infra.sandbox (hardened agent + proxy, GPU)."""
import json
import os
import subprocess
import uuid

import pytest

from infra import sandbox as sbx

pytestmark = pytest.mark.docker
AGENT_IMAGE = "wsp-agent-base:step1"


def dk(*a, check=True):
    return subprocess.run(["docker", *map(str, a)], text=True, capture_output=True, check=check)


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    t = tmp_path_factory.mktemp("sbx")
    for d in ("ws", "pool", "labels", "models", "external"):
        (t / d).mkdir()
    (t / "ws").chmod(0o777)
    (t / "pool/img1.txt").write_text("pool")
    (t / "labels/labels.csv").write_text("a,b\n")
    (t / "models/m.txt").write_text("m")
    (t / "external/e.txt").write_text("e")
    (t / "corpus.json").write_text(json.dumps({"archive_sha256": "b" * 64, "raw_sha256": [], "normalized_sha256": [],
                                              "phash": {"pool": [], "test": []}, "basenames": ["248388-1.jpg", "1-1.jpg", "2-2.jpg"]}))
    run = "t" + uuid.uuid4().hex[:8]
    spec = sbx.SandboxSpec(run, t / "ws", t / "pool", t / "labels", t / "models", t / "external", AGENT_IMAGE,
                           t / "state", t / "corpus.json", gpu_mem_cap_gib=2.0, cpus=2, memory="8g")
    sb = sbx.create(spec)
    try:
        yield t, spec, sb
    finally:
        sbx.destroy(sb)
        assert not leftovers(run)


def leftovers(run):
    out = []
    out += dk("ps", "-a", "--filter", f"label=wsp.run={run}", "-q").stdout.split()
    out += dk("network", "ls", "--filter", f"label=wsp.run={run}", "-q").stdout.split()
    return out


def ex(sb, *cmd, user=sbx.AGENT_UID_GID, check=False):
    return subprocess.run(sbx.exec_argv(sb, list(cmd), user=user), text=True, capture_output=True)


def test_names_and_networks(env):
    t, spec, sb = env
    assert (sb.container, sb.proxy, sb.network) == tuple(f"wsp-{k}-{spec.run_id}" for k in ("agent", "proxy", "int"))
    nets = json.loads(dk("inspect", "-f", "{{json .NetworkSettings.Networks}}", sb.container).stdout)
    assert list(nets) == [sb.network]
    pn = json.loads(dk("inspect", "-f", "{{json .NetworkSettings.Networks}}", sb.proxy).stdout)
    assert set(pn) == {sb.network, "wsp-egress"}
    ni = json.loads(dk("network", "inspect", sb.network).stdout)[0]
    assert ni["Internal"] is True
    assert ni["Options"]["com.docker.network.bridge.gateway_mode_ipv4"] == "isolated"
    assert dk("inspect", "-f", "{{json .NetworkSettings.Ports}}", sb.container).stdout.strip() in ("{}", "null")


def test_hardening(env):
    t, spec, sb = env
    i = json.loads(dk("inspect", sb.container).stdout)[0]
    hc = i["HostConfig"]
    assert i["Config"]["User"] == "1004:1004"
    assert hc["CapDrop"] == ["ALL"] and not hc["CapAdd"]
    assert "no-new-privileges" in " ".join(hc["SecurityOpt"])
    assert hc["ReadonlyRootfs"] and not hc["Privileged"]
    assert hc["PidsLimit"] == 4096 and hc["Memory"] == 8 * 2**30 and hc["MemorySwap"] == hc["Memory"]
    assert hc["NanoCpus"] == 2 * 10**9 and hc["ShmSize"] == 16 * 2**30
    assert hc["NetworkMode"] == sb.network and hc["PidMode"] == "" and hc["IpcMode"] in ("private", "")
    assert not hc["PortBindings"] and hc["Tmpfs"]["/tmp"].startswith("rw,size=16g")
    assert hc["DeviceRequests"][0]["DeviceIDs"] == ["0"]
    mounts = {m["Destination"]: m for m in i["Mounts"]}
    assert set(mounts) == {"/workspace", "/inputs/pool", "/inputs/labels", "/inputs/models", "/inputs/external", "/opt/wsp-ca"}
    for d, m in mounts.items():
        assert m["RW"] == (d == "/workspace"), d
        assert "docker.sock" not in m["Source"] and "locked" not in m["Source"]
    assert mounts["/opt/wsp-ca"]["Source"].endswith("/public")
    # exec view
    assert ex(sb, "id", "-u").stdout.strip() == "1004" and ex(sb, "id", "-g").stdout.strip() == "1004"
    assert "CapEff:\t0000000000000000" in ex(sb, "cat", "/proc/self/status").stdout
    assert "NoNewPrivs:\t1" in ex(sb, "cat", "/proc/self/status").stdout
    assert ex(sb, "touch", "/etc/x").returncode != 0
    assert ex(sb, "touch", "/workspace/home/ok").returncode == 0
    assert (t / "ws/home/ok").exists()
    assert ex(sb, "touch", "/tmp/ok").returncode == 0
    for d in ("pool", "labels", "models", "external"):
        assert ex(sb, "touch", f"/inputs/{d}/x").returncode != 0
    assert ex(sb, "cat", "/inputs/pool/img1.txt").stdout == "pool"
    assert ex(sb, "ls", "/inputs/labels").stdout.split() == ["labels.csv"]
    assert ex(sb, "touch", "/opt/wsp-ca/x").returncode != 0
    assert ex(sb, "ls", "/var/run/docker.sock").returncode != 0
    assert ex(sb, "sh", "-c", "ls /var/run/docker.sock /run/docker.sock /ca /home 2>&1; test -e /var/lib/wsp-ca").returncode != 0
    assert ex(sb, "ls", "/opt/wsp-ca").stdout.split() == ["bundle.pem", "ca.pem"]
    # pid 1 is tini; exec'd work never pid 1
    assert ex(sb, "cat", "/proc/1/comm").stdout.strip() == "tini"
    assert ex(sb, "sh", "-c", "echo $$").stdout.strip() != "1"


def test_env(env):
    t, spec, sb = env
    e = dict(l.split("=", 1) for l in ex(sb, "env").stdout.splitlines() if "=" in l)
    url = f"http://{sb.proxy}:8080"
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        assert e[k] == url, k
    assert e["NO_PROXY"] == "localhost,127.0.0.1"
    for k in sbx.CA_ENV:
        assert e[k] == "/opt/wsp-ca/bundle.pem", k
    assert e["HOME"] == "/workspace/home"
    assert not [k for k in e if "KEY" in k or "TOKEN" in k or "SECRET" in k]
    assert ex(sb, "pwd").stdout.strip() == "/workspace"
    assert ex(sb, "sh", "-c", "echo $PWD", ).stdout.strip() == "/workspace"


def test_proxy_only_egress(env):
    t, spec, sb = env
    r = ex(sb, "curl", "-sS", "--max-time", "40", "-o", "/dev/null", "-w", "%{http_code}", "https://pypi.org/simple/")
    assert r.stdout == "200", r.stderr
    r = ex(sb, "curl", "-sS", "--max-time", "40", "-o", "/dev/null", "-w", "%{http_code}", "https://huggingface.co/")
    assert r.stdout in ("200", "301", "302"), r.stderr
    r = ex(sb, "curl", "-sS", "--max-time", "40", "-o", "/dev/null", "-w", "%{http_code}",
           "https://github.com/ninglitony/Benchmark-for-MFXR")
    assert r.stdout == "403"
    # bypass attempts
    r = ex(sb, "curl", "-sS", "--noproxy", "*", "--max-time", "6", "https://1.1.1.1/")
    assert r.returncode != 0
    r = ex(sb, "curl", "-sS", "--noproxy", "*", "--max-time", "6", "https://pypi.org/")
    assert r.returncode != 0
    py = ("import socket,sys\ns=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(4)\n"
          "s.sendto(b'\\x12\\x34\\x01\\x00\\x00\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x07example\\x03com\\x00\\x00\\x01\\x00\\x01',('8.8.8.8',53))\n"
          "try:\n s.recvfrom(512);print('GOT')\nexcept Exception as e:print('FAIL')\n")
    assert ex(sb, "python3", "-c", py).stdout.strip() in ("FAIL", "") 
    gw = dk("inspect", "-f", "{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}", sb.container).stdout.strip()
    assert gw in ("", "invalid IP")  # docker renders an unset gateway as "invalid IP"
    for host in ("172.17.0.1", "10.0.0.1", "192.168.1.1"):
        assert ex(sb, "curl", "-sS", "--noproxy", "*", "--max-time", "4", f"http://{host}/").returncode != 0
    # proxy refuses private destinations
    r = ex(sb, "curl", "-sS", "--max-time", "20", "-o", "/dev/null", "-w", "%{http_code}", "http://172.17.0.1:2375/")
    assert r.stdout == "403", (r.stdout, r.stderr)
    logs = (t / "state/proxy/requests.jsonl").read_text()
    assert '"pypi.org"' in logs and "403" in logs
    assert "?" not in logs.replace("\\?", "")  # no query strings logged


def test_pip_user_install_through_proxy(env):
    t, spec, sb = env
    r = ex(sb, "pip", "install", "--user", "--no-input", "--disable-pip-version-check", "humanize==4.12.3")
    assert r.returncode == 0, r.stderr[-800:]
    r = ex(sb, "python3", "-c", "import humanize;print(humanize.__file__)")
    assert "/workspace/home/.local" in r.stdout, r.stderr


def test_gpu(env):
    t, spec, sb = env
    assert ex(sb, "nvidia-smi", "-L").stdout.count("GPU 0") == 1
    r = ex(sb, "python3", "-c", "import torch;x=torch.ones(2,2,device='cuda');print(float((x@x).sum()))")
    assert r.stdout.strip() == "8.0", r.stderr[-500:]


def test_exec_argv_shape(env):
    t, spec, sb = env
    assert sbx.exec_argv(sb, ["ls", "-l"], workdir="/tmp") == [
        "docker", "exec", "--user", "1004:1004", "--workdir", "/tmp", sb.container, "ls", "-l"]
    with pytest.raises(sbx.SandboxError):
        sbx.exec_argv(sb, [])


def test_pause_unpause(env):
    t, spec, sb = env
    p = subprocess.Popen(sbx.exec_argv(sb, ["sh", "-c", "touch /tmp/started; sleep 3; echo done"]), text=True, stdout=subprocess.PIPE)
    import time
    for _ in range(50):
        if ex(sb, "test", "-e", "/tmp/started").returncode == 0:
            break
        time.sleep(0.2)
    sbx.pause(sb)
    assert ex(sb, "true").returncode != 0  # frozen: exec refused
    assert dk("inspect", "-f", "{{.State.Paused}}", sb.container).stdout.strip() == "true"
    assert dk("inspect", "-f", "{{.State.Running}}", sb.proxy).stdout.strip() == "true"
    sbx.unpause(sb)
    assert dk("inspect", "-f", "{{.State.Paused}}", sb.container).stdout.strip() == "false"
    assert p.communicate(timeout=30)[0].strip() == "done"


def test_validation(tmp_path, env):
    t, spec, sb = env
    import dataclasses
    with pytest.raises(sbx.SandboxError):
        sbx.create(dataclasses.replace(spec, run_id="Bad Id;"))
    (t / "labels/extra.csv").write_text("x")
    try:
        with pytest.raises(sbx.SandboxError):
            sbx.create(dataclasses.replace(spec, run_id="v" + spec.run_id))
    finally:
        (t / "labels/extra.csv").unlink()
    with pytest.raises(sbx.SandboxError, match="already exists"):
        sbx.create(spec)
    assert dk("inspect", sb.container, check=False).returncode == 0


def test_destroy_idempotent_and_scoped(tmp_path):
    """Separate sandbox: destroy twice, never touches unrelated wsp-* resources; failed create cleans up."""
    t = tmp_path
    for d in ("ws", "pool", "labels", "models", "external"):
        (t / d).mkdir()
    (t / "corpus.json").write_text("{}")
    run = "d" + uuid.uuid4().hex[:8]
    bystander = f"wsp-bystander-{run}"
    # a bystander container and a same-named-but-unlabelled network must be untouched
    dk("run", "-d", "--name", bystander, "--entrypoint", "sleep", AGENT_IMAGE, "infinity")
    dk("network", "create", f"wsp-int-{run}")  # unlabelled: create() must refuse, destroy() must not remove
    spec = sbx.SandboxSpec(run, t / "ws", t / "pool", t / "labels", t / "models", t / "external", AGENT_IMAGE,
                           t / "state", t / "corpus.json", gpus=None)
    try:
        with pytest.raises(sbx.SandboxError, match="already exists"):
            sbx.create(spec)
        sbx.destroy(sbx.names(run))
        assert dk("network", "inspect", f"wsp-int-{run}", check=False).returncode == 0
        dk("network", "rm", f"wsp-int-{run}")
        sb = sbx.create(spec)  # no GPU
        assert not (dk("inspect", "-f", "{{.HostConfig.DeviceRequests}}", sb.container).stdout.strip() not in ("[]", "<nil>"))
        sbx.destroy(sb)
        sbx.destroy(sb)
        assert not leftovers(run)
        assert dk("inspect", "-f", "{{.State.Running}}", bystander).stdout.strip() == "true"
    finally:
        dk("rm", "-f", bystander, check=False)
        dk("network", "rm", f"wsp-int-{run}", check=False)
        sbx.destroy(sbx.names(run))


def test_cli(tmp_path):
    t = tmp_path
    for d in ("ws", "pool", "labels", "models", "external"):
        (t / d).mkdir()
    (t / "corpus.json").write_text("{}")
    run = "c" + uuid.uuid4().hex[:8]
    base = ["python", "-m", "infra.sandbox"]
    try:
        r = subprocess.run([*base, "create", "--run-id", run, "--workspace", t / "ws", "--pool-dir", t / "pool",
                            "--labels-dir", t / "labels", "--models-dir", t / "models", "--external-dir", t / "external",
                            "--image", AGENT_IMAGE, "--state-dir", t / "state", "--hash-corpus", t / "corpus.json",
                            "--cpus", "1", "--memory", "4g", "--gpu-mem-cap-gib", "3"], text=True, capture_output=True,
                           env={**os.environ})
        assert r.returncode == 0, r.stderr
        info = json.loads(r.stdout)
        assert info["container"] == f"wsp-agent-{run}" and info["gpu_watchdog_arg"] == f"wsp-agent-{run}:3"
        a = subprocess.run([*base, "exec-argv", "--run-id", run, "echo", "hi"], text=True, capture_output=True)
        argv = json.loads(a.stdout)
        assert subprocess.run(argv, text=True, capture_output=True).stdout.strip() == "hi"
        subprocess.run([*base, "pause", "--run-id", run], check=True)
        subprocess.run([*base, "unpause", "--run-id", run], check=True)
    finally:
        subprocess.run([*base, "destroy", "--run-id", run], check=True)
        subprocess.run([*base, "destroy", "--run-id", run], check=True)
    assert not leftovers(run)
