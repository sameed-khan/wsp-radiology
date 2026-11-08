"""Step 6: end-to-end suite for spec section 4 "Tests", in ONE real GPU-enabled sandbox topology.

Everything runs through infra.sandbox.create(): hardened agent (GPU) on an internal network, policy proxy
dual-homed to wsp-egress. A synthetic test server on wsp-egress serves synthetic content; its (private) IP is
exempted only via the TEST-ONLY proxy flags. All requests are issued from INSIDE the agent container as uid 1004.
Run: uv run --extra test pytest -m docker tests/infra/test_e2e_sandbox_docker.py -s
"""
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid

import imagehash
import pytest

from infra import sandbox as sbx
from test_proxy_policy_step3 import NAMES, OTHER, SECRET, SECRET_JPEG, encode, norm_sha, tarred, zipped
from test_proxy_policy_step3_docker import SERVER, junk
from test_watcher import POOL_IM, POOL_JPG, TEST_IM, TEST_JPG, make_image
from test_watcher import NAMES as WNAMES, enc as wenc, ph as wph, sha as wsha

pytestmark = pytest.mark.docker
AGENT_IMAGE = "wsp-agent:phase1"
PROXY_IMAGE = "wsp-proxy:phase1"
CAP_GIB = 0.05
CANARY = "E2E-CANARY-DO-NOT-LEAK"


def dk(*a, check=True, input=None):
    return subprocess.run(["docker", *map(str, a)], text=True, capture_output=True, check=check, input=input)


def events(p):
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


class E:
    pass


@pytest.fixture(scope="module")
def e2e(tmp_path_factory):
    t = tmp_path_factory.mktemp("e2e")
    run = "e" + uuid.uuid4().hex[:8]
    srv = f"wsp-testsrv-{run}"
    for d in ("ws", "pool", "labels", "models", "external", "srv", "locked"):
        (t / d).mkdir()
    (t / "ws").chmod(0o777)
    (t / "pool/p.txt").write_text("pool")
    (t / "labels/labels.csv").write_text("a,b\n")
    (t / "models/m.txt").write_text("m")
    (t / "external/e.txt").write_text("e")
    (t / "locked/canary.txt").write_text(CANARY)  # sibling of the mounted dirs, never mounted
    cred = t / "fake-credentials.json"
    cred.write_text(CANARY)
    # one corpus for proxy AND watcher: SECRET = a "test-split" image; POOL_IM = pool image
    corpus = {"archive_sha256": "b" * 64,
              "raw_sha256": [hashlib.sha256(SECRET_JPEG).hexdigest(), wsha(TEST_JPG), wsha(POOL_JPG)],
              "normalized_sha256": [norm_sha(SECRET)],
              "phash": {"pool": [str(imagehash.phash(SECRET)), wph(POOL_IM)], "test": [wph(TEST_IM)]},
              "basenames": NAMES + WNAMES}
    (t / "corpus.json").write_text(json.dumps(corpus))
    files = {
        "clean.jpg": encode(OTHER), "secret.jpg": SECRET_JPEG,
        "reenc.jpg": encode(SECRET.resize((128, 96)), quality=60),
        "secret.zip": zipped({"d/x.jpg": SECRET_JPEG}),
        "blob.parquet": b"PAR1" + junk(4000) + b"\0" + SECRET_JPEG + junk(1000),
        "names.txt": "\n".join(NAMES[:4]).encode(), "two.txt": "\n".join(NAMES[:2]).encode(),
        "hello.txt": b"hello",
    }
    for n, d in files.items():
        (t / "srv" / n).write_bytes(d)
    created_egress = False
    sb = None
    try:
        if dk("network", "inspect", "wsp-egress", check=False).returncode:
            dk("network", "create", "wsp-egress")
            created_egress = True
        dk("run", "-d", "--name", srv, "--label", f"wsp.test={run}", "--network", "wsp-egress", "-v", f"{t/'srv'}:/srv:ro",
           "--entrypoint", "python", PROXY_IMAGE, "-c", SERVER)
        ip = dk("inspect", "-f", '{{(index .NetworkSettings.Networks "wsp-egress").IPAddress}}', srv).stdout.strip()
        assert ip
        spec = sbx.SandboxSpec(run, t / "ws", t / "pool", t / "labels", t / "models", t / "external", AGENT_IMAGE,
                               t / "state", t / "corpus.json", gpu_mem_cap_gib=CAP_GIB, cpus=2, memory="8g",
                               proxy_image=PROXY_IMAGE, test_allow_ips=(ip,))
        sb = sbx.create(spec)
        x = E()
        x.t, x.spec, x.sb, x.srv, x.ip, x.run = t, spec, sb, srv, ip, run
        x.plog = spec.state_dir / "proxy" / "requests.jsonl"

        def ex(*cmd, **kw):
            return subprocess.run(sbx.exec_argv(sb, list(cmd), **kw), text=True, capture_output=True)

        def fetch(url, out="/tmp/out", *extra, timeout=60):
            """curl from inside the agent; returns (http_code, body-or-None)."""
            r = ex("curl", "-sS", "--max-time", str(timeout), "-o", out, "-w", "%{http_code}", *extra, url)
            body = subprocess.run(sbx.exec_argv(sb, ["head", "-c", "4000", out]), capture_output=True).stdout.decode(
                "utf-8", "replace") if r.stdout.strip() else None
            return r.stdout.strip(), body

        x.ex, x.fetch = ex, fetch
        for _ in range(60):  # proxy readiness
            if fetch(f"http://{srv}:8000/hello.txt")[0] == "200":
                break
            time.sleep(1)
        yield x
    finally:
        if sb:
            sbx.destroy(sb)
        dk("rm", "-f", srv, check=False)
        if created_egress:
            dk("network", "rm", "wsp-egress", check=False)
        left = dk("ps", "-a", "--filter", f"label=wsp.run={run}", "-q").stdout.split()
        left += dk("network", "ls", "--filter", f"label=wsp.run={run}", "-q").stdout.split()
        assert not left, left


def u(x, name):
    return f"http://{x.srv}:8000/{name}"


# 1. allowed HTTPS through the proxy -------------------------------------------------------------------------
@pytest.mark.parametrize("url,ok", [("https://pypi.org/simple/", {"200"}), ("https://huggingface.co/", {"200", "301", "302"}),
                                    ("https://github.com/pypa/pip", {"200", "301", "302"})])
def test_allowed_https(e2e, url, ok):
    code, _ = e2e.fetch(url)
    assert code in ok, (url, code)
    # python requests and git over the proxy as well
    r = e2e.ex("python3", "-c", "import requests;print(requests.get('https://pypi.org/simple/pip/',timeout=40).status_code)")
    assert r.stdout.strip() == "200", r.stderr[-300:]
    r = e2e.ex("git", "ls-remote", "https://github.com/pypa/pip", "HEAD")
    assert r.returncode == 0 and "HEAD" in r.stdout, r.stderr[-300:]


# 2. denied MFXR URLs -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("url", [
    "https://github.com/ninglitony/Benchmark-for-MFXR", "https://github.com/NingLiTony/benchmark-for-mfxr/archive/refs/heads/main.zip",
    "https://api.github.com/repos/ninglitony/Benchmark-for-MFXR/zipball",
    "https://raw.githubusercontent.com/ninglitony/Benchmark-for-MFXR/main/README.md",
    "https://codeload.github.com/ninglitony/Benchmark-for-MFXR/zip/refs/heads/main",
    "https://figshare.com/articles/dataset/x/30335941", "https://api.figshare.com/v2/articles/30335941",
    "https://ndownloader.figshare.com/files/66766667", "https://doi.org/10.6084/m9.figshare.30335941",
    "https://github.com/ninglitony%2FBenchmark-for-MFXR//", "https://r.jina.ai/https://example.com/",
])
def test_mfxr_urls_denied(e2e, url):
    code, body = e2e.fetch(url)
    assert code == "403", (url, code)
    assert body and "blocked by sandbox policy" in body.lower(), body


def test_mfxr_redirect_chain_denied(e2e):
    assert e2e.fetch(u(e2e, "r/gh"), "/tmp/o", "-L")[0] == "403"
    assert e2e.fetch(u(e2e, "r/fig"), "/tmp/o", "-L")[0] == "403"


# 3. direct egress bypass fails -------------------------------------------------------------------------------
def test_bypass_fails(e2e):
    ex = e2e.ex
    for url in ("https://1.1.1.1/", "https://pypi.org/", "http://93.184.216.34/"):
        assert ex("curl", "-sS", "--noproxy", "*", "--max-time", "6", url).returncode != 0, url
    py = ("import socket\ns=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(4)\n"
          "s.sendto(b'\\x12\\x34\\x01\\x00\\x00\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x07example\\x03com\\x00\\x00\\x01\\x00\\x01',('8.8.8.8',53))\n"
          "try:\n s.recvfrom(512);print('GOT')\nexcept Exception:print('FAIL')\n")
    assert ex("python3", "-c", py).stdout.strip() != "GOT"
    assert ex("python3", "-c", "import socket;socket.gethostbyname('pypi.org')").returncode != 0  # no DNS from internal net
    gw = dk("inspect", "-f", "{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}", e2e.sb.container).stdout.strip()
    assert gw in ("", "invalid IP")
    hostips = [ln.split()[3].split("/")[0] for ln in subprocess.run(["ip", "-4", "-o", "addr"], text=True,
               capture_output=True).stdout.splitlines() if len(ln.split()) > 3]
    for h in {*hostips, "172.17.0.1", "172.18.0.1"}:
        if h.startswith("127."):
            continue
        for port in (22, 80, 2375):
            assert ex("curl", "-sS", "--noproxy", "*", "--max-time", "3", f"http://{h}:{port}/").returncode != 0, (h, port)
    # other egress-bridge neighbours are unreachable directly too (agent has no route to wsp-egress)
    assert ex("curl", "-sS", "--noproxy", "*", "--max-time", "4", f"http://{e2e.ip}:8000/hello.txt").returncode != 0
    assert ex("curl", "-sS", "--noproxy", "*", "--max-time", "4", "http://wsp-egress/").returncode != 0


# 4. private destinations refused -----------------------------------------------------------------------------
@pytest.mark.parametrize("url", ["http://10.0.0.1/", "http://172.17.0.1:2375/", "http://192.168.1.1/",
                                 "http://169.254.169.254/latest/meta-data", "http://100.64.0.1/", "http://[fd00::1]/"])
def test_private_destinations_refused(e2e, url):
    code, _ = e2e.fetch(url, "/tmp/o", "--proxy", f"http://{e2e.sb.proxy}:8080", timeout=20)
    assert code == "403", (url, code)


def test_private_after_redirect_refused(e2e):
    for r in ("lo", "meta", "dec", "ten"):
        assert e2e.fetch(u(e2e, f"r/{r}"), "/tmp/o", "-L")[0] == "403", r


def test_private_exemption_is_test_only_and_flagged(e2e):
    recs = [json.loads(x) for x in e2e.plog.read_text().splitlines()]
    assert recs and all(r.get("test_mode") is True for r in recs)  # test flag visible in every record


# 5. synthetic hash corpus ------------------------------------------------------------------------------------
def test_clean_allowed(e2e):
    for n in ("clean.jpg", "two.txt", "hello.txt"):
        assert e2e.fetch(u(e2e, n))[0] == "200", n


@pytest.mark.parametrize("name", ["secret.jpg", "reenc.jpg", "secret.zip", "blob.parquet", "names.txt"])
def test_corpus_content_blocked_and_not_saved(e2e, name):
    out = f"/workspace/dl-{name}"
    code, _ = e2e.fetch(u(e2e, name), out)
    assert code == "403", (name, code)
    size = e2e.ex("sh", "-c", f"wc -c < {out}").stdout.strip()
    assert size and int(size) < 400  # only the short explanation, never the content
    assert e2e.ex("grep", "-c", "^PAR1\\|\xff\xd8", out).stdout.strip() in ("0", "")


def test_proxy_logs_sanitized(e2e):
    text = e2e.plog.read_text()
    assert CANARY not in text
    for n in NAMES:
        assert n not in text
    rules = {json.loads(x).get("rule_id") for x in text.splitlines()}
    assert {"sha256", "phash", "basenames"} <= {r for r in rules if r}, rules
    assert "Cookie" not in text and "User-Agent" not in text


# 6. GPU inside the agent -------------------------------------------------------------------------------------
def test_gpu_in_agent(e2e):
    assert e2e.ex("nvidia-smi", "-L").stdout.count("GPU 0") == 1
    r = e2e.ex("python3", "-c", "import torch;x=torch.ones(3,3,device='cuda');print(float((x@x).sum()), torch.cuda.is_available())")
    assert r.stdout.split() == ["27.0", "True"], r.stderr[-400:]


# 7. watcher --------------------------------------------------------------------------------------------------
def test_watcher_detections_and_pool_derivatives(e2e):
    x = e2e
    spec, ctl = x.spec, x.spec.state_dir / "control"
    st = x.t / "ws" / ".stage"
    st.mkdir(exist_ok=True)

    def agent_put(rel, data):
        (st / "f").write_bytes(data)
        r = x.ex("sh", "-c", f'mkdir -p "$(dirname /workspace/{rel})" && cp /workspace/.stage/f /workspace/{rel}')
        assert r.returncode == 0, r.stderr
        (st / "f").unlink()

    agent_put("res/ok.jpg", wenc(make_image(4321)))
    agent_put("res/pool_small.jpg", wenc(POOL_IM.resize((140, 100)), quality=50))
    agent_put("res/report.txt", b"nothing here")
    argv = [sys.executable, "-m", "infra.watcher", "--workspace", str(spec.workspace), "--corpus", str(spec.hash_corpus),
            "--state-dir", str(spec.state_dir / "watcher"), "--control-dir", str(ctl), "--interval", "3600", "--run-id", spec.run_id]
    proc = subprocess.Popen(argv)
    log = spec.state_dir / "watcher" / "watcher.jsonl"

    def wait(pred, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            if pred():
                return True
            time.sleep(0.5)
        return False

    def scans():
        return sum(1 for ev in events(log) if ev.get("event") == "scan")

    try:
        assert wait(lambda: scans() >= 1)
        fnd = {ev["file"]: (ev["level"], ev["rule"]) for ev in events(log) if ev.get("event") == "finding"}
        assert fnd == {"res/pool_small.jpg": ("info", "pool-derivative")}, fnd
        assert not (ctl / "STOP_REQUEST.json").exists()
        # A resized test-near image alerts, not stops.
        n = scans()
        agent_put("res/near-zero.png", wenc(TEST_IM.resize((128, 96)), "PNG"))
        proc.send_signal(signal.SIGUSR1)
        assert wait(lambda: scans() > n)
        assert any(ev.get("file") == "res/near-zero.png" and ev.get("level") == "alert" for ev in events(log))
        assert not (ctl / "STOP_REQUEST.json").exists()
        # alert-only band: pHash distance 3-6 from the test image
        n = scans()
        alert = TEST_IM.copy()
        import numpy as np
        from PIL import Image
        for dx in range(2, 40):
            arr = np.array(TEST_IM).copy()
            arr[10:10 + dx * 2, 10:10 + dx * 2] = 255 - arr[10:10 + dx * 2, 10:10 + dx * 2]
            cand = Image.fromarray(arr)
            d = imagehash.phash(cand) - imagehash.phash(TEST_IM)
            if 3 <= d <= 6:
                alert = cand
                break
        else:
            pytest.fail("could not build an alert-band image")
        agent_put("res/near.png", wenc(alert, "PNG"))
        proc.send_signal(signal.SIGUSR1)
        assert wait(lambda: scans() > n)
        assert ("alert" in {ev.get("level") for ev in events(log) if ev.get("file") == "res/near.png"}), events(log)[-3:]
        assert not (ctl / "STOP_REQUEST.json").exists()
        # stop-level: test-split derivative (exact bytes)
        n = scans()
        agent_put("res/leak.jpg", TEST_JPG)
        proc.send_signal(signal.SIGUSR1)
        assert wait((ctl / "STOP_REQUEST.json").exists)
        req = json.loads((ctl / "STOP_REQUEST.json").read_text())
        assert req["file"] == "res/leak.jpg" and set(req) >= {"reason", "file", "rule", "time"}
        # basenames in a text file (fresh control dir semantics: a second stop still logs)
        agent_put("res/names.txt", "\n".join(WNAMES[:4]).encode())
        proc.send_signal(signal.SIGUSR1)
        assert wait(lambda: any(ev.get("rule") == "basenames" for ev in events(log)))
        text = log.read_text()
        for s in (wsha(TEST_JPG), wph(TEST_IM), *WNAMES):
            assert s not in text
        # host-only: not visible in the agent
        assert x.ex("sh", "-c", f"ls {ctl} {spec.state_dir} 2>&1").returncode != 0
    finally:
        proc.kill()
        proc.wait()


# 8. no credentials / docker socket / locked paths ------------------------------------------------------------
def test_nothing_sensitive_visible(e2e):
    x = e2e
    mi = x.ex("cat", "/proc/self/mountinfo").stdout
    dests = [ln.split()[4] for ln in mi.splitlines()]
    srcs = " ".join(ln.split()[3] for ln in mi.splitlines())
    for bad in ("docker.sock", "locked", ".pi", ".ssh", "wsp-ca/private", "/var/lib/wsp-ca", "ca/private"):
        assert bad not in mi, bad
    assert not [d for d in dests if d.startswith(("/state", "/var/run", "/run/docker", "/home", "/root"))], dests
    assert "/state/proxy" not in srcs and "/state/watcher" not in srcs and "/state/gpu" not in srcs
    r = x.ex("sh", "-c", "find / -xdev \\( -name 'docker.sock' -o -name 'canary.txt' -o -name 'fake-credentials.json' "
                         "-o -name hash-corpus.json -o -name 'corpus.json' -o -name 'ca-key*' -o -name '*.p12' \\) "
                         "-not -path '/proc/*' 2>/dev/null; find /inputs /workspace /opt -name '*.pem' 2>/dev/null")
    found = [p for p in r.stdout.split() if not p.endswith(("/bundle.pem", "/ca.pem"))]
    assert not found, found
    assert x.ex("sh", "-c", f"grep -rIl {CANARY} /workspace /inputs /opt /tmp /etc 2>/dev/null").stdout.strip() == ""
    assert sorted(x.ex("ls", "/inputs").stdout.split()) == ["external", "labels", "models", "pool"]
    assert x.ex("ls", "/inputs/labels").stdout.split() == ["labels.csv"]
    assert x.ex("sh", "-c", "ls -d /inputs/pool/.. /inputs/../root /root /home/* 2>&1 | head -3").returncode in (0, 1, 2)
    assert x.ex("sh", "-c", "cat /opt/wsp-ca/*.pem | grep -c PRIVATE").stdout.strip() == "0"
    env = x.ex("env").stdout
    assert CANARY not in env and not [k for k in env.splitlines() if any(w in k.split("=")[0] for w in ("KEY", "TOKEN", "SECRET", "PASSWORD", "ANTHROPIC", "AWS"))]
    assert x.ex("sh", "-c", "test -S /var/run/docker.sock").returncode != 0
    assert x.ex("curl", "-sS", "--noproxy", "*", "--max-time", "3", "--unix-socket", "/var/run/docker.sock", "http://d/info").returncode != 0
    # the proxy's private CA dir and the host state are not reachable from the agent's network either
    assert x.ex("curl", "-sS", "--noproxy", "*", "--max-time", "3", f"http://{x.sb.proxy}:8081/").returncode != 0


# 9. GPU watchdog (last: it kills any CUDA context above the artificially tiny cap) ---------------------------
TORCH_ALLOC = ("import torch; x=torch.ones(64*1024*1024,device='cuda'); print('ready',flush=True)\n"
               "while True:\n  x=x*1.0001\n  torch.cuda.synchronize()")


def test_gpu_watchdog_kills_over_cap_process(e2e):
    x = e2e
    state = x.spec.state_dir / "gpu"
    wd = subprocess.Popen([sys.executable, "-m", "infra.gpu_watchdog", "--state-dir", str(state),
                           "--sandbox-json", str(x.spec.state_dir / "sandbox.json")])
    p = subprocess.Popen(sbx.exec_argv(x.sb, ["python3", "-c", TORCH_ALLOC]), stdout=subprocess.PIPE, text=True)
    try:
        assert p.stdout.readline().strip() == "ready"
        log = state / "gpu-watchdog.jsonl"
        end = time.time() + 60
        while time.time() < end and not any(ev["event"] in ("violation", "kill-failed") for ev in events(log)):
            time.sleep(1)
        v = [ev for ev in events(log) if ev["event"] == "violation"]
        assert v and v[0]["container"] == x.sb.container and v[0]["memory_mib"] > CAP_GIB * 1024
        assert p.wait(timeout=30) != 0
        assert dk("inspect", "-f", "{{.State.Running}}", x.sb.container).stdout.strip() == "true"
        assert x.ex("echo", "alive").stdout.strip() == "alive"
        assert x.ex("pgrep", "-f", "torch").returncode != 0
    finally:
        wd.kill()
        wd.wait()
        p.kill()
        x.ex("pkill", "-9", "-f", "torch")
