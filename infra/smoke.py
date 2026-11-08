#!/usr/bin/env python3
"""Offline containment smoke test; emits a JSON report, never launches an agent."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import uuid

ROOT = pathlib.Path(__file__).resolve().parent
PROJECT = "wsp-sandbox-smoke-" + uuid.uuid4().hex[:12]


def run(args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, **kwargs)


def main():
    checks = {}
    details = {}
    with tempfile.TemporaryDirectory(prefix="wsp-sandbox-") as workspace:
        # nobody needs access to the single disposable bind mount.
        os.chmod(workspace, 0o777)
        env = dict(os.environ, SANDBOX_WORKSPACE=workspace)
        compose = ["docker", "compose", "-p", PROJECT, "-f", str(ROOT / "compose.yaml")]
        try:
            build = run(compose + ["up", "-d", "--build"], env=env, timeout=600)
            details["build"] = (build.stdout + build.stderr)[-5000:]
            checks["build_and_start"] = build.returncode == 0
            if not checks["build_and_start"]:
                return checks, details
            cid = run(compose + ["ps", "-q", "sandbox"], env=env, timeout=30).stdout.strip()
            inspect = run(["docker", "inspect", cid], timeout=30, check=True)
            container = json.loads(inspect.stdout)[0]
            host = container["HostConfig"]
            mounts = container["Mounts"]
            checks["mounts_workspace_only"] = (len(mounts) == 1 and mounts[0]["Destination"] == "/workspace" and pathlib.Path(mounts[0]["Source"]).resolve() == pathlib.Path(workspace).resolve())
            checks["hardening"] = (container["Config"]["User"] == "65534:65534" and host["ReadonlyRootfs"] and "ALL" in host["CapDrop"] and "no-new-privileges:true" in host["SecurityOpt"] and host["NetworkMode"] != "host" and not host["Privileged"])
            networks = container["NetworkSettings"]["Networks"]
            checks["single_network"] = len(networks) == 1
            network_id = next(iter(networks.values()))["NetworkID"]
            network = json.loads(run(["docker", "network", "inspect", network_id], timeout=30, check=True).stdout)[0]
            checks["isolated_internal_network"] = network["Internal"] and network["Options"].get("com.docker.network.bridge.gateway_mode_ipv4") == "isolated"
            checks["no_gateway"] = all(not item.get("Gateway") and not item.get("IPv6Gateway") for item in networks.values())
            # A closed host port is not evidence of isolation: require no route.
            host_ips = run(["hostname", "-I"], timeout=10, check=True).stdout.split()
            checks["host_addresses_discovered"] = bool(host_ips)
            details["host_addresses"] = host_ips
            program = r'''import errno, json, os, socket, subprocess, sys
r={}
targets = [("public_ip", "1.1.1.1"), ("private_ip", "10.255.255.1")]
targets += [("host_ip_" + str(i), ip) for i, ip in enumerate(json.loads(sys.argv[1])) if ":" not in ip]
for name, host in targets:
    s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(3)
    try: s.connect((host,443)); r[name]=False
    except OSError as e: r[name]=e.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH)
    finally: s.close()
s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try: s.sendto(b"dns-probe", ("1.1.1.1",53)); r["udp_dns_no_route"]=False
except OSError as e: r["udp_dns_no_route"]=e.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH)
finally: s.close()
try: socket.getaddrinfo("example.com",443); r["hostname_dns"]=False
except OSError: r["hostname_dns"]=True
p=subprocess.run(["curl","--noproxy","*","--connect-timeout","3","--max-time","5","https://1.1.1.1/"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
r["curl_direct"]=p.returncode == 7
try:
    open("/rootfs-write-probe", "w").close(); r["root_read_only"]=False
except OSError: r["root_read_only"]=True
try:
    open("/workspace/probe", "w").close(); open("/tmp/probe", "w").close(); r["writable_paths"]=True
except OSError: r["writable_paths"]=False
print(json.dumps(r))'''
            test = run(compose + ["exec", "-T", "sandbox", "python3", "-c", program, json.dumps(host_ips)], env=env, timeout=45)
            details["container_test_stderr"] = test.stderr
            checks["container_test_executed"] = test.returncode == 0
            if test.returncode == 0:
                checks.update(json.loads(test.stdout))
            versions = run(compose + ["exec", "-T", "sandbox", "sh", "-c", "python3 --version; curl --version | head -1; dpkg-query -W -f='${Package} ${Version}\\n' ca-certificates"], env=env, timeout=30)
            details["versions"] = versions.stdout.strip()
        except (subprocess.SubprocessError, OSError, ValueError, KeyError, IndexError) as exc:
            checks["test_error"] = False
            details["error"] = str(exc)
        finally:
            cleanup = run(compose + ["down", "--remove-orphans", "--rmi", "local"], env=env, timeout=120)
            checks["cleanup"] = cleanup.returncode == 0
            details["cleanup"] = (cleanup.stdout + cleanup.stderr)[-2000:]
    return checks, details


if __name__ == "__main__":
    checks, details = main()
    print(json.dumps({"scope": "offline-containment-only", "project": PROJECT, "checks": checks, "details": details, "passed": bool(checks) and all(checks.values())}, indent=2))
    sys.exit(0 if checks and all(checks.values()) else 1)
