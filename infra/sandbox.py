"""Networked sandbox lifecycle (spec section 4): internal network + policy proxy + hardened agent.

API used by the harness (lane L3):
    create(spec) -> Sandbox; pause/unpause/destroy(sb); exec_argv(sb, argv, user=..., workdir=...)
CLI: python -m infra.sandbox create|destroy|pause|unpause|exec-argv ...

Every Docker resource carries the label ``wsp.run=<run_id>`` and the name suffix ``<run_id>``;
destroy() only removes resources that carry that label, so it never touches anything else.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

EGRESS_NETWORK = "wsp-egress"
DEFAULT_PROXY_IMAGE = "wsp-proxy:step3"
AGENT_UID_GID = "1004:1004"
PROXY_PORT = 8080
CA_ENV = ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE", "PIP_CERT", "NODE_EXTRA_CA_CERTS", "GIT_SSL_CAINFO")
_RUN_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,39}$")


@dataclass
class SandboxSpec:
    run_id: str
    workspace: Path
    pool_dir: Path
    labels_dir: Path
    models_dir: Path
    external_dir: Path
    image: str
    state_dir: Path  # host-only: proxy logs, CA copy, watcher/gpu logs
    hash_corpus: Path
    gpu_mem_cap_gib: float = 11.0
    cpus: float = 10
    memory: str = "28g"
    # optional extras
    proxy_image: str = DEFAULT_PROXY_IMAGE
    ca_dir: Path | None = None  # host-only dir holding private/ and public/ (default: state_dir/ca)
    upstream_ca: Path | None = Path("/etc/ssl/certs/ca-certificates.crt")  # proxy upstream trust (None: certifi)
    gpus: str | None = "device=0"  # None disables GPU (tests only)
    test_allow_ips: tuple[str, ...] = ()  # TEST ONLY: exempt IPs from private-destination refusal
    proxy_extra_env: tuple[str, ...] = ()  # TEST ONLY: KEY=VALUE


@dataclass
class Sandbox:
    run_id: str
    container: str
    proxy: str
    network: str


class SandboxError(RuntimeError):
    pass


def names(run_id: str) -> Sandbox:
    return Sandbox(run_id, f"wsp-agent-{run_id}", f"wsp-proxy-{run_id}", f"wsp-int-{run_id}")


def _check_run_id(run_id: str) -> None:
    if not _RUN_RE.match(run_id):
        raise SandboxError(f"invalid run_id {run_id!r}: must match {_RUN_RE.pattern}")


def _docker(*args, check=True, timeout=300) -> subprocess.CompletedProcess:
    r = subprocess.run(["docker", *map(str, args)], text=True, capture_output=True, timeout=timeout)
    if check and r.returncode:
        raise SandboxError(f"docker {' '.join(map(str, args[:3]))} failed: {r.stderr.strip()[:500]}")
    return r


def _label(run_id: str) -> list[str]:
    return ["--label", f"wsp.run={run_id}", "--label", "wsp.managed=1"]


def _owned(kind: str, name: str, run_id: str) -> bool:
    """True only if resource exists and carries our run label."""
    r = _docker(kind, "inspect", "-f", '{{index .Config.Labels "wsp.run"}}' if kind == "container"
                else '{{index .Labels "wsp.run"}}', name, check=False)
    return r.returncode == 0 and r.stdout.strip() == run_id


def _ensure_ca(spec: SandboxSpec) -> tuple[Path, Path]:
    from infra.proxy.ca import generate
    base = Path(spec.ca_dir) if spec.ca_dir else spec.state_dir / "ca"
    private, public = base / "private", base / "public"
    if not (private / "mitmproxy-ca.pem").is_file() or not (public / "bundle.pem").is_file():
        if private.exists() or public.exists():
            raise SandboxError(f"incomplete CA directory {base}; remove it to regenerate")
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        generate(private, public)
    return private, public


def _validate(spec: SandboxSpec) -> dict[str, Path]:
    _check_run_id(spec.run_id)
    paths = {
        "pool": Path(spec.pool_dir).resolve(), "labels": Path(spec.labels_dir).resolve(),
        "models": Path(spec.models_dir).resolve(), "external": Path(spec.external_dir).resolve(),
        "corpus": Path(spec.hash_corpus).resolve(),
    }
    for k in ("pool", "labels", "models", "external"):
        if not paths[k].is_dir():
            raise SandboxError(f"{k} directory missing: {paths[k]}")
    if not paths["corpus"].is_file():
        raise SandboxError(f"hash corpus missing: {paths['corpus']}")
    extra = sorted(p.name for p in paths["labels"].iterdir() if p.name != "labels.csv")
    if extra:
        raise SandboxError("labels_dir must contain only labels.csv; found other entries")
    if not (0 < spec.gpu_mem_cap_gib <= 24):
        raise SandboxError("gpu_mem_cap_gib out of range")
    if os.path.realpath(spec.state_dir) == os.path.realpath(spec.workspace) or \
            Path(spec.workspace).resolve() in Path(spec.state_dir).resolve().parents:
        raise SandboxError("state_dir must not be inside the agent workspace")
    for k in ("pool", "labels", "models", "external"):
        if "locked" in paths[k].parts or paths[k] == Path("/var/run") or "docker.sock" in str(paths[k]):
            raise SandboxError(f"{k} directory must not be a locked/private location")
    return paths


def create(spec: SandboxSpec) -> Sandbox:
    paths = _validate(spec)
    sb = names(spec.run_id)
    for kind, n in (("container", sb.container), ("container", sb.proxy), ("network", sb.network)):
        if _docker(kind, "inspect", n, check=False).returncode == 0:
            raise SandboxError(f"{kind} {n} already exists")
    state = Path(spec.state_dir)
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state, 0o700)
    ws = Path(spec.workspace)
    (ws / "home").mkdir(parents=True, exist_ok=True)
    private, public = _ensure_ca(spec)
    logs = state / "proxy"
    logs.mkdir(mode=0o700, exist_ok=True)
    lab = _label(spec.run_id)
    try:
        if _docker("network", "inspect", EGRESS_NETWORK, check=False).returncode:
            _docker("network", "create", EGRESS_NETWORK)
        _docker("network", "create", "--internal", "--opt", "com.docker.network.bridge.gateway_mode_ipv4=isolated",
                *lab, sb.network)
        # --- proxy: internal + egress; runs as the host user so it can read the 0700 CA dir
        penv = ["-e", f"WSP_RUN_ID={spec.run_id}", "-e", "HOME=/tmp"]
        if spec.upstream_ca:
            penv += ["-e", "WSP_UPSTREAM_CA=/etc/wsp/upstream-ca.pem"]
        if spec.test_allow_ips:
            penv += ["-e", "WSP_TEST_MODE=1", "-e", "WSP_TEST_ALLOW_IPS=" + ",".join(spec.test_allow_ips)]
        for kv in spec.proxy_extra_env:
            penv += ["-e", kv]
        pmounts = ["-v", f"{private}:/var/lib/wsp-ca", "-v", f"{logs}:/var/log/wsp",
                   "-v", f"{paths['corpus']}:/etc/wsp/hash-corpus.json:ro"]
        if spec.upstream_ca:
            pmounts += ["-v", f"{Path(spec.upstream_ca).resolve()}:/etc/wsp/upstream-ca.pem:ro"]
        _docker("run", "-d", "--name", sb.proxy, "--network", sb.network, *lab,
                "--user", f"{os.getuid()}:{os.getgid()}", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:rw,size=1g,mode=1777",
                "--pids-limit", "1024", "--memory", "8g", "--restart", "no", *pmounts, *penv, spec.proxy_image)
        _docker("network", "connect", "--gw-priority", "1", EGRESS_NETWORK, sb.proxy)
        # --- agent: internal network only
        url = f"http://{sb.proxy}:{PROXY_PORT}"
        bundle = "/opt/wsp-ca/bundle.pem"
        aenv = {"HOME": "/workspace/home", "NO_PROXY": "localhost,127.0.0.1", "no_proxy": "localhost,127.0.0.1",
                "WSP_RUN_ID": spec.run_id}
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            aenv[k] = url
        for k in CA_ENV:
            aenv[k] = bundle
        envargs = [x for k, v in aenv.items() for x in ("-e", f"{k}={v}")]
        gpu = ["--gpus", spec.gpus] if spec.gpus else []
        _docker("run", "-d", "--name", sb.container, "--network", sb.network, *lab,
                "--user", AGENT_UID_GID, "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--read-only", "--tmpfs", "/tmp:rw,size=16g,mode=1777,nosuid,nodev", "--shm-size", "16g",
                "--pids-limit", "4096", "--memory", spec.memory, "--memory-swap", spec.memory,
                "--cpus", str(spec.cpus), *gpu, "--workdir", "/workspace", "--restart", "no",
                "-v", f"{ws.resolve()}:/workspace",
                "-v", f"{paths['pool']}:/inputs/pool:ro", "-v", f"{paths['labels']}:/inputs/labels:ro",
                "-v", f"{paths['models']}:/inputs/models:ro", "-v", f"{paths['external']}:/inputs/external:ro",
                "-v", f"{public}:/opt/wsp-ca:ro", *envargs, spec.image)
        _wait_ready(sb)
        (state / "sandbox.json").write_text(json.dumps({
            "run_id": spec.run_id, "container": sb.container, "proxy": sb.proxy, "network": sb.network,
            "gpu_watchdog_arg": f"{sb.container}:{spec.gpu_mem_cap_gib:g}", "created": time.time()}))
        return sb
    except BaseException:
        destroy(sb)
        raise


def _wait_ready(sb: Sandbox, timeout: float = 90.0) -> None:
    """Proxy must accept TCP from the agent's network position, and the agent must be running."""
    probe = (f"import socket,sys; s=socket.create_connection(({sb.proxy!r},{PROXY_PORT}),3); s.close()")
    end = time.time() + timeout
    while time.time() < end:
        for n in (sb.proxy, sb.container):
            st = _docker("inspect", "-f", "{{.State.Running}}", n, check=False).stdout.strip()
            if st != "true":
                logs = _docker("logs", "--tail", "20", n, check=False)
                raise SandboxError(f"{n} not running: {(logs.stdout + logs.stderr)[-400:]}")
        if _docker("exec", sb.container, "python3", "-c", probe, check=False).returncode == 0:
            return
        time.sleep(1)
    raise SandboxError("proxy not reachable from agent before timeout")


def pause(sb: Sandbox) -> None:
    """Freeze the agent (all processes). The proxy keeps running so logs/in-flight policy continue."""
    _docker("pause", sb.container)


def unpause(sb: Sandbox) -> None:
    _docker("unpause", sb.container)


def destroy(sb: Sandbox) -> None:
    """Idempotent: remove agent, proxy and network of this run (only if labelled for this run)."""
    for n in (sb.container, sb.proxy):
        if _owned("container", n, sb.run_id):
            _docker("rm", "-f", n, check=False)
    if _owned("network", sb.network, sb.run_id):
        _docker("network", "rm", sb.network, check=False)


def exec_argv(sb: Sandbox, argv: list[str], user: str = AGENT_UID_GID, workdir: str = "/workspace",
              interactive: bool = False) -> list[str]:
    """docker exec argv for running ``argv`` in the agent container (never as PID 1; tini is PID 1)."""
    if not argv:
        raise SandboxError("empty argv")
    return ["docker", "exec", *(["-i"] if interactive else []), "--user", user, "--workdir", workdir,
            sb.container, *map(str, argv)]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m infra.sandbox")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    for f in ("run-id", "workspace", "pool-dir", "labels-dir", "models-dir", "external-dir", "image", "state-dir",
              "hash-corpus"):
        c.add_argument("--" + f, required=True)
    c.add_argument("--gpu-mem-cap-gib", type=float, default=11.0)
    c.add_argument("--cpus", type=float, default=10)
    c.add_argument("--memory", default="28g")
    c.add_argument("--proxy-image", default=DEFAULT_PROXY_IMAGE)
    c.add_argument("--ca-dir")
    for name in ("destroy", "pause", "unpause"):
        sub.add_parser(name).add_argument("--run-id", required=True)
    e = sub.add_parser("exec-argv")
    e.add_argument("--run-id", required=True)
    e.add_argument("--user", default=AGENT_UID_GID)
    e.add_argument("--workdir", default="/workspace")
    e.add_argument("command", nargs="+")
    a = p.parse_args(argv)
    if a.cmd == "create":
        spec = SandboxSpec(a.run_id, Path(a.workspace), Path(a.pool_dir), Path(a.labels_dir), Path(a.models_dir),
                           Path(a.external_dir), a.image, Path(a.state_dir), Path(a.hash_corpus),
                           a.gpu_mem_cap_gib, a.cpus, a.memory, proxy_image=a.proxy_image,
                           ca_dir=Path(a.ca_dir) if a.ca_dir else None)
        sb = create(spec)
        print(json.dumps({**sb.__dict__, "gpu_watchdog_arg": f"{sb.container}:{a.gpu_mem_cap_gib:g}"}))
        return 0
    _check_run_id(a.run_id)
    sb = names(a.run_id)
    if a.cmd == "destroy":
        destroy(sb)
    elif a.cmd == "pause":
        pause(sb)
    elif a.cmd == "unpause":
        unpause(sb)
    else:
        print(json.dumps(exec_argv(sb, a.command, a.user, a.workdir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
