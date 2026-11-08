"""Live policy tests through the real proxy container (spec section 4 tests).

Topology: internal network (client + proxy), egress bridge `wsp-egress` (proxy + a
synthetic test server). The test server has a private IP, so the *test proxy*
runs with the TEST-ONLY exemption WSP_TEST_MODE=1/WSP_TEST_ALLOW_IPS for exactly
that IP. A second, production-configured proxy (no test flags) proves the
exemption is inert without them.
"""
import json
import subprocess
import textwrap
import time
import uuid

import pytest

from infra.proxy.ca import generate
from test_proxy_policy_step3 import (NAMES, OTHER, SECRET, SECRET_JPEG, encode, norm_sha, tarred, zipped)
import hashlib
import imagehash
import random

pytestmark = pytest.mark.docker
PROXY_IMAGE = "wsp-proxy:phase1"
AGENT_IMAGE = "wsp-agent:phase1"
MAX_BODY = 3_000_000

SERVER = textwrap.dedent('''
    import http.server, socketserver, threading, os, socket
    ROOT = "/srv"
    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *a): pass
        def do_GET(self):
            p = self.path.split("?")[0]
            if p.startswith("/r/"):
                T = {"gh": "https://github.com/ninglitony/benchmark-for-mfxr/zip/main",
                     "fig": "https://ndownloader.figshare.com/files/66766667",
                     "lo": "http://127.0.0.1:8000/x", "meta": "http://169.254.169.254/latest/meta-data",
                     "dec": "http://2130706433/", "ten": "http://10.0.0.1/",
                     "ok": "/clean.jpg", "sec": "/secret.jpg"}
                self.send_response(302); self.send_header("Location", T[p[3:]]); self.send_header("Content-Length", "0"); self.end_headers(); return
            if p == "/gzsecret":
                import gzip
                data = gzip.compress(open(ROOT + "/secret.jpg", "rb").read())
                self.send_response(200); self.send_header("Content-Encoding", "gzip"); self.send_header("Content-Length", str(len(data)))
                self.end_headers(); self.wfile.write(data); return
            if p == "/chunked":
                self.send_response(200); self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
                for _ in range(8):
                    self.wfile.write(b"%x\\r\\n" % 500000 + b"a" * 500000 + b"\\r\\n")
                self.wfile.write(b"0\\r\\n\\r\\n"); return
            if p == "/range":
                rng = self.headers.get("Range")
                self.send_response(206 if rng else 200); self.send_header("Content-Length", "5"); self.end_headers(); self.wfile.write(b"hello"); return
            if p == "/rangeseen":
                body = ("range=" + str(self.headers.get("Range"))).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            try:
                data = open(ROOT + p, "rb").read()
            except OSError:
                self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers(); self.wfile.write(data)
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0)); self.rfile.read(n)
            self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"ok")
    class T(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
    def raw():
        s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("0.0.0.0", 9000)); s.listen()
        while True:
            c, _ = s.accept(); c.sendall(b"RAW-SERVICE-BANNER\\n"); c.close()
    threading.Thread(target=raw, daemon=True).start()
    T(("0.0.0.0", 8000), H).serve_forever()
''')


def docker(*args, check=True, input=None):
    return subprocess.run(["docker", *map(str, args)], text=True, capture_output=True, check=check, input=input)


def junk(n, seed=3):
    rnd = random.Random(seed)
    return bytes(rnd.randrange(256) for _ in range(n))


@pytest.fixture(scope="module")
def topo(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("topo")
    suffix = uuid.uuid4().hex[:8]
    net, srv, client = f"wsp-int-{suffix}", f"wsp-testsrv-{suffix}", f"wsp-client-{suffix}"
    proxies = {"test": f"wsp-proxy-t-{suffix}", "prod": f"wsp-proxy-p-{suffix}", "nocorp": f"wsp-proxy-n-{suffix}"}
    private, public = tmp / "private", tmp / "public"
    generate(private, public)
    corpus = tmp / "hash-corpus.json"
    corpus.write_text(json.dumps({
        "archive_sha256": "b" * 64,
        "raw_sha256": [hashlib.sha256(SECRET_JPEG).hexdigest()],
        "normalized_sha256": [norm_sha(SECRET)],
        "phash": {"pool": [str(imagehash.phash(SECRET))], "test": []},
        "basenames": NAMES}))
    srv_dir = tmp / "srv"
    srv_dir.mkdir()
    files = {
        "clean.jpg": encode(OTHER),
        "secret.jpg": SECRET_JPEG,
        "reenc.jpg": encode(SECRET.resize((128, 96)), quality=60),
        "secret.zip": zipped({"d/x.jpg": SECRET_JPEG}),
        "secret.tar": tarred({"x.txt": b"hi", "p/y.jpg": encode(SECRET, quality=40)}),
        "blob.parquet": b"PAR1" + junk(4000) + b"\0" + SECRET_JPEG + junk(1000),
        "names.txt": "\n".join(NAMES[:4]).encode(),
        "two.txt": "\n".join(NAMES[:2]).encode(),
        "clean.zip": zipped({"a.jpg": encode(OTHER), "n.txt": b"fine"}),
        "bomb.gz": __import__("gzip").compress(b"\0" * (4_000_000)),
        "hello.txt": b"hello",
    }
    for n, d in files.items():
        (srv_dir / n).write_bytes(d)
    logs = {k: tmp / f"logs-{k}" for k in proxies}
    created_egress = False
    try:
        if docker("network", "inspect", "wsp-egress", check=False).returncode:
            docker("network", "create", "wsp-egress")
            created_egress = True
        docker("network", "create", "--internal", "--opt", "com.docker.network.bridge.gateway_mode_ipv4=isolated", net)
        docker("run", "-d", "--name", srv, "--network", "wsp-egress", "-v", f"{srv_dir}:/srv:ro",
               "--entrypoint", "python", PROXY_IMAGE, "-c", SERVER)
        srv_ip = docker("inspect", "-f", "{{(index .NetworkSettings.Networks \"wsp-egress\").IPAddress}}", srv).stdout.strip()
        assert srv_ip
        for kind, name in proxies.items():
            logs[kind].mkdir()
            env = ["-e", f"WSP_RUN_ID={kind}"]
            corpus_mount = ["-v", f"{corpus}:/etc/wsp/hash-corpus.json:ro"] if kind != "nocorp" else []
            if kind in ("test", "nocorp"):
                env += ["-e", f"WSP_MAX_BODY={MAX_BODY}", "-e", "WSP_MAX_UNCOMPRESSED=3000000", "-e", "WSP_TEST_MODE=1", "-e", f"WSP_TEST_ALLOW_IPS={srv_ip}"]
            docker("run", "-d", "--name", name, "--network", net, "-v", f"{private}:/var/lib/wsp-ca",
                   "-v", f"{logs[kind]}:/var/log/wsp", *corpus_mount,
                   "-v", "/etc/ssl/certs/ca-certificates.crt:/etc/wsp/upstream-ca.pem:ro",
                   "-e", "WSP_UPSTREAM_CA=/etc/wsp/upstream-ca.pem", *env, PROXY_IMAGE)
            docker("network", "connect", "--gw-priority", "1", "wsp-egress", name)
        docker("run", "-d", "--name", client, "--network", net, "-v", f"{public}:/opt/wsp-ca:ro",
               "--entrypoint", "sleep", AGENT_IMAGE, "infinity")

        class T:
            pass
        t = T()
        t.srv, t.srv_ip, t.logs, t.proxies, t.client = srv, srv_ip, logs, proxies, client

        def curl(url, kind="test", *extra, method=None, timeout=30):
            cmd = ["exec", client, "curl", "-sS", "--max-time", str(timeout), "--proxy", f"http://{proxies[kind]}:8080",
                   "--cacert", "/opt/wsp-ca/bundle.pem", "-o", "/tmp/out", "-w", "%{http_code}", *extra, url]
            r = docker(*cmd, check=False)
            return r.stdout.strip(), r
        t.curl = curl

        def curl_body(url, kind="test", *extra):
            code, r = curl(url, kind, *extra)
            body = docker("exec", client, "cat", "/tmp/out", check=False).stdout
            return code, body
        t.curl_body = curl_body

        def records(kind="test"):
            p = logs[kind] / "requests.jsonl"
            return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
        t.records = records
        # wait until the proxy answers
        for _ in range(60):
            code, _ = curl(f"http://{srv}:8000/hello.txt")
            if code == "200":
                break
            time.sleep(1)
        assert code == "200", docker("logs", proxies["test"], check=False)
        yield t
    finally:
        docker("rm", "-f", client, srv, *proxies.values(), check=False)
        docker("network", "rm", net, check=False)
        if created_egress:
            docker("network", "rm", "wsp-egress", check=False)


def u(t, name):
    return f"http://{t.srv}:8000/{name}"


def test_clean_content_allowed(topo):
    for name in ("clean.jpg", "clean.zip", "two.txt", "hello.txt"):
        assert topo.curl(u(topo, name))[0] == "200", name


@pytest.mark.parametrize("name,rule", [
    ("secret.jpg", "sha256"), ("reenc.jpg", "phash"), ("secret.zip", "sha256"), ("secret.tar", "phash"),
    ("blob.parquet", "sha256"), ("names.txt", "basenames"), ("bomb.gz", "archive-limit"),
])
def test_content_blocked(topo, name, rule):
    code, body = topo.curl_body(u(topo, name))
    assert code == "403", (name, code)
    assert rule in body
    row = [r for r in topo.records() if r["path"] == "/" + name][-1]
    assert row["verdict"] == "blocked" and row["rule_id"] == rule and row["status"] == 200
    assert row["content_sha256"] and row["response_size"] > 0


def test_content_encoded_body_is_decoded_and_scanned(topo):
    code, body = topo.curl_body(u(topo, "gzsecret"))
    assert code == "403" and "sha256" in body


def test_missing_corpus_fails_closed(topo):
    code, body = topo.curl_body(u(topo, "hello.txt"), "nocorp")
    assert code == "403" and "policy-unavailable" in body
    assert topo.curl("https://pypi.org/simple/", "nocorp")[0] in ("403", "000")


def test_body_size_limit_fail_closed(topo):
    code, _ = topo.curl(u(topo, "chunked"))
    assert code != "200"   # chunked stream larger than the limit is never delivered
    rows = [r for r in topo.records() if r["path"] == "/chunked"]
    assert rows and all(r["verdict"] == "blocked" for r in rows)
    print("chunked over-limit:", code, [r["rule_id"] for r in rows])


def test_range_stripped_and_206_blocked(topo):
    code, body = topo.curl_body(u(topo, "rangeseen"), "test", "-H", "Range: bytes=0-10")
    assert code == "200" and body == "range=None"
    code, _ = topo.curl(u(topo, "range"))
    assert code == "200"


def test_upload_basenames(topo):
    code, _ = topo.curl(u(topo, "x"), "test", "--data-binary", "\n".join(NAMES[:3]))
    assert code == "403"
    code, _ = topo.curl(u(topo, "x"), "test", "--data-binary", "\n".join(NAMES[:2]))
    assert code == "200"
    # uploading raw image bytes is not content-blocked (basenames check only)
    topo_file = "/tmp/up.bin"
    docker("exec", "-i", topo.client, "sh", "-c", f"cat > {topo_file}", input="not an image")
    assert topo.curl(u(topo, "x"), "test", "--data-binary", f"@{topo_file}")[0] == "200"


@pytest.mark.parametrize("url", [
    "http://figshare.com/articles/dataset/x/30335941",
    "https://api.figshare.com/v2/articles/30335941?private_marker=SECRETQ",
    "https://ndownloader.figshare.com/files/66766667",
    "https://doi.org/10.6084/m9.figshare.30335941",
    "https://github.com/ninglitony/Benchmark-for-MFXR",
    "https://github.com/NingLiTony/Benchmark-for-MFXR/archive/refs/heads/main.zip",
    "https://raw.githubusercontent.com/ninglitony/Benchmark-for-MFXR/main/README.md",
    "https://codeload.github.com/ninglitony/benchmark-for-mfxr/zip/main",
    "https://api.github.com/repos/ninglitony/Benchmark-for-MFXR",
    "https://cdn.jsdelivr.net/gh/ninglitony/Benchmark-for-MFXR@main/x",
    "https://r.jina.ai/https://example.com",
    "https://web.archive.org/web/2020/https://figshare.com/",
    "https://api.tavily.com/extract",
])
@pytest.mark.parametrize("kind", ["prod"])
def test_mfxr_urls_denied_403(topo, url, kind):
    # Denial happens before any upstream connection, so no internet is needed.
    code, _ = topo.curl(url, kind)
    assert code == "403", url
    text = (topo.logs[kind] / "requests.jsonl").read_text()
    assert "SECRETQ" not in text and "private_marker" not in text


def test_host_header_spoof_does_not_evade(topo):
    # CONNECT target is the real figshare host; the Host header lies. The URL is still matched
    # against the connection's real name.
    code, body = topo.curl_body("https://ndownloader.figshare.com/files/66766667", "prod", "-H", "Host: example.com")
    assert code == "403" and "mfxr-figshare" in body


def test_mfxr_https_connect_path_denied(topo):
    # Same denial through TLS interception (CONNECT then inner request).
    code, body = topo.curl_body("https://github.com/ninglitony/Benchmark-for-MFXR", "prod")
    assert code == "403" and "mfxr-repository" in body


def test_redirect_to_denied_url_blocked(topo):
    code, body = topo.curl_body(u(topo, "r/gh"))
    assert code == "403" and "redirect-mfxr-repository" in body
    code, body = topo.curl_body(u(topo, "r/fig"))
    assert code == "403" and "redirect-mfxr-figshare" in body


def test_redirect_to_private_blocked(topo):
    for key in ("lo", "meta", "dec", "ten"):
        code, body = topo.curl_body(u(topo, "r/" + key))
        assert code == "403" and "redirect-private-destination" in body, (key, code, body)


def test_redirect_followed_checked_each_hop(topo):
    assert topo.curl(u(topo, "r/ok"), "test", "-L")[0] == "200"
    assert topo.curl(u(topo, "r/sec"), "test", "-L")[0] == "403"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/", "http://localhost:8000/", "http://169.254.169.254/latest/meta-data/",
    "http://2130706433/", "http://0x7f.1/", "http://10.0.0.1/", "http://192.168.1.1/", "http://172.17.0.1:2375/",
    "http://100.100.100.200/", "http://[::1]/", "http://[fd00:ec2::254]/", "http://0.0.0.0:8000/",
    "https://127.0.0.1/", "https://localhost/",
])
def test_private_destinations_refused(topo, url):
    code, r = topo.curl(url, "prod", timeout=15)
    if url.startswith("https"):   # refused at CONNECT: curl reports the tunnel failure
        assert code == "000" and "403" in r.stderr, (url, code, r.stderr)
    else:
        assert code == "403", (url, code)
    assert any(x["rule_id"] == "private-destination" for x in topo.records("prod"))


def test_private_destination_logged_and_exempt_only_in_test_mode(topo):
    # Production proxy refuses the very same test server that the test proxy reaches.
    code, body = topo.curl_body(u(topo, "hello.txt"), "prod")
    assert code == "403" and "private-destination" in body
    assert topo.curl(u(topo, "hello.txt"), "test")[0] == "200"
    rows = topo.records("prod")
    assert any(r["rule_id"] == "private-destination" for r in rows)
    assert all("test_mode" not in r for r in rows)
    assert all(r.get("test_mode") for r in topo.records("test"))


def test_private_destination_https_connect_refused(topo):
    code, body = topo.curl_body(f"https://{topo.srv}:8000/hello.txt", "prod")
    assert code == "000" or code == "403"
    r = topo.curl(f"https://127.0.0.1/", "prod")[1]
    assert "403" in r.stderr or r.stdout.strip() in ("403", "000")


def test_raw_tcp_blocked(topo):
    # CONNECT to a non-HTTP service (test server banner on port 9000) via the test proxy.
    r = docker("exec", topo.client, "curl", "-sS", "--max-time", "8", "--proxytunnel", "--proxy",
               f"http://{topo.proxies['test']}:8080", f"telnet://{topo.srv}:9000", check=False)
    assert "RAW-SERVICE-BANNER" not in r.stdout
    print("raw tcp curl rc/stderr:", r.returncode, r.stderr.strip()[:200])
    assert r.stdout == ""


def test_real_internet_allowed_via_prod_proxy(topo):
    # Real HTTPS to the allowed sites through the production-configured proxy.
    # github.com is intermittently unreachable from this host even *directly*
    # (corporate firewall); a github failure only counts if a direct fetch works.
    unreachable = []
    for url, path in (("https://pypi.org/simple/", "/simple/"),
                      ("https://huggingface.co/api/models/bert-base-uncased", "/api/models/bert-base-uncased"),
                      ("https://github.com/robots.txt", "/robots.txt")):
        for _attempt in range(3):
            code, r = topo.curl(url, "prod", "-L", timeout=40)
            if code == "200":
                break
        if code != "200" and "github" in url:
            direct = docker("run", "--rm", "--entrypoint", "curl", AGENT_IMAGE, "-sS", "-L", "-o", "/dev/null",
                            "-w", "%{http_code}", "--max-time", "40", url, check=False).stdout.strip()
            if direct != "200":
                unreachable.append(url)
                continue
        assert code == "200", (url, code, r.stderr)
    rows = [r for r in topo.records("prod") if r["host"] in ("pypi.org", "huggingface.co", "github.com")
            and r["status"] == 200]
    hosts = {r["host"] for r in rows}
    assert {"pypi.org", "huggingface.co"} <= hosts
    if not unreachable:
        assert "github.com" in hosts
    print("direct-unreachable (skipped):", unreachable)
    assert all(r["verdict"] == "allowed" and "?" not in r["path"] for r in rows)


def test_pip_download_through_policy_proxy(topo):
    env = ["-e", f"HTTPS_PROXY=http://{topo.proxies['prod']}:8080", "-e", "PIP_CERT=/opt/wsp-ca/bundle.pem"]
    r = docker("exec", *env, topo.client, "python3", "-m", "pip", "download", "--no-deps", "-d", "/tmp/dl",
               "humanize==4.12.3", check=False)
    assert r.returncode == 0, r.stderr[-1500:]


def test_logs_sanitized(topo):
    for kind in ("test", "prod"):
        for row in topo.records(kind):
            assert set(row) >= {"time", "run_id", "method", "scheme", "host", "path", "url_sha256", "status",
                                "request_size", "response_size", "content_sha256", "verdict", "rule_id"}
            assert "?" not in row["path"]
            assert not (set(row) & {"headers", "cookies", "query", "body", "url"})
