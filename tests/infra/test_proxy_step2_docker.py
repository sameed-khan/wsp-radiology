"""Live Step 2 transport test; this proxy intentionally has no security policy."""
import json
from pathlib import Path
import subprocess
import time
import uuid

import pytest

from infra.proxy.ca import generate


def docker(*args, check=True):
    return subprocess.run(["docker", *map(str, args)], text=True, capture_output=True, check=check)


@pytest.mark.docker
def test_proxy_transport(tmp_path):
    suffix = uuid.uuid4().hex[:10]
    net, proxy, client = (f"wsp-{kind}-{suffix}" for kind in ("int", "proxy", "client"))
    private, public, logs = tmp_path / "private", tmp_path / "public", tmp_path / "logs"
    generate(private, public)
    logs.mkdir()
    assert private.stat().st_mode & 0o777 == 0o700
    assert (private / "mitmproxy-ca.pem").stat().st_mode & 0o777 == 0o600
    created_egress = False
    try:
        if docker("network", "inspect", "wsp-egress", check=False).returncode:
            docker("network", "create", "wsp-egress")
            created_egress = True
        docker("network", "create", "--internal", "--opt", "com.docker.network.bridge.gateway_mode_ipv4=isolated", net)
        docker("run", "-d", "--name", proxy, "--network", net,
               "-v", f"{private}:/var/lib/wsp-ca", "-v", f"{logs}:/var/log/wsp",
               "-e", f"WSP_RUN_ID={suffix}", "wsp-proxy:step2")
        docker("network", "connect", "--gw-priority", "1", "wsp-egress", proxy)
        docker("run", "-d", "--name", client, "--network", net,
               "-v", f"{public}:/opt/wsp-ca:ro", "--entrypoint", "sleep", "wsp-agent-base:step1", "infinity")
        env = ["-e", f"HTTPS_PROXY=http://{proxy}:8080", "-e", f"HTTP_PROXY=http://{proxy}:8080",
               "-e", "REQUESTS_CA_BUNDLE=/opt/wsp-ca/bundle.pem", "-e", "SSL_CERT_FILE=/opt/wsp-ca/bundle.pem",
               "-e", "CURL_CA_BUNDLE=/opt/wsp-ca/bundle.pem", "-e", "PIP_CERT=/opt/wsp-ca/bundle.pem"]
        for _ in range(40):
            result = docker("exec", *env, client, "curl", "-fsS", "--max-time", "5", "-o", "/dev/null", "https://pypi.org/simple/", check=False)
            if result.returncode == 0:
                break
            time.sleep(1)
        assert result.returncode == 0, result.stderr
        untrusted = docker("exec", "-e", f"HTTPS_PROXY=http://{proxy}:8080", client, "curl", "-fsS", "--max-time", "10", "-o", "/dev/null", "https://pypi.org/simple/", check=False)
        assert untrusted.returncode != 0, "TLS interception unexpectedly trusted without our CA"
        docker("exec", *env, client, "python3", "-c", "import requests; r=requests.get('https://pypi.org/simple/?wsp_secret_marker=private',timeout=30); r.raise_for_status()")
        docker("exec", *env, client, "python3", "-m", "pip", "download", "--no-deps", "--index-url", "https://pypi.org/simple", "-d", "/tmp", "humanize==4.12.3")
        addresses = set(subprocess.run(["hostname", "-I"], capture_output=True, text=True, check=True).stdout.split())
        addresses.add("1.1.1.1")
        # Docker's conventional default bridge gateway, even if absent on the isolated bridge.
        addresses.add("172.17.0.1")
        script = '''import socket,sys
for ip in sys.argv[1:]:
 s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(2)
 try: s.connect((ip,443))
 except OSError: pass
 else: raise SystemExit('direct TCP succeeded: '+ip)
 finally: s.close()
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(2)
try:
 s.sendto(bytes.fromhex('1234010000010000000000000470797069036f72670000010001'),('8.8.8.8',53))
 s.recvfrom(512)
except OSError: pass
else: raise SystemExit('direct DNS succeeded')
try: print('external DNS:', socket.getaddrinfo('pypi.org',443)[0][4][0])
except OSError as e: print('external DNS failed:', e)
'''
        result = docker("exec", client, "python3", "-c", script, *sorted(ip for ip in addresses if ":" not in ip))
        print(result.stdout.strip())
        records = [json.loads(line) for line in (logs / "requests.jsonl").read_text().splitlines()]
        assert any(row["host"] == "pypi.org" and row["status"] == 200 for row in records)
        assert all(row["verdict"] == "unfiltered" and "?" not in row["path"] for row in records)
        assert "wsp_secret_marker" not in (logs / "requests.jsonl").read_text()
    finally:
        docker("rm", "-f", client, proxy, check=False)
        docker("network", "rm", net, check=False)
        if created_egress:
            docker("network", "rm", "wsp-egress", check=False)
