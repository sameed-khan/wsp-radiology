"""Host-side GPU memory enforcement for explicitly named containers.

This is a best-effort watchdog, not a GPU memory partition: the polling
interval permits transient overages and processes may exit between samples.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import time
from datetime import datetime, timezone


def _run(*argv: str) -> str:
    return subprocess.check_output(argv, text=True, stderr=subprocess.PIPE)


def _log(path: Path, **event: object) -> None:
    event["time"] = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")


def _processes() -> list[tuple[int, int]]:
    output = _run("nvidia-smi", "--query-compute-apps=pid,used_memory",
                  "--format=csv,noheader,nounits")
    processes = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) != 2:
            raise ValueError("unexpected nvidia-smi process output")
        try:
            processes.append((int(parts[0].strip()), int(parts[1].strip())))
        except ValueError:
            # e.g. "[N/A]" memory: unknown, skip rather than abort the whole poll
            continue
    return processes


def _process_uid(pid: int) -> int:
    """Real UID of a host PID (0 if unreadable).

    The sandbox drops every capability, so `docker exec -u 0` has no CAP_KILL and
    cannot signal the agent's UID-1004 processes: the kill must run as the victim's UID.
    """
    try:
        match = re.search(r"^Uid:\s+(\d+)", Path(f"/proc/{pid}/status").read_text(), re.MULTILINE)
        return int(match.group(1)) if match else 0
    except (OSError, ValueError):
        return 0


def _utilization() -> dict[int, int]:
    """Return the sampled SM utilization per host PID, when NVIDIA reports it."""
    output = _run("nvidia-smi", "pmon", "-c", "1", "-s", "u")
    result = {}
    for line in output.splitlines():
        fields = line.split()
        if not fields or line.lstrip().startswith("#"):
            continue
        if len(fields) < 4:
            raise ValueError("unexpected nvidia-smi pmon output")
        if fields[1].isdigit() and fields[3].isdigit():
            pid, utilization = int(fields[1]), int(fields[3])
            result[pid] = result.get(pid, 0) + utilization
    return result


def _container_pid(pid: int, container_id: str) -> int | None:
    """Return the innermost namespace PID only for a matching cgroup."""
    try:
        cgroup = Path(f"/proc/{pid}/cgroup").read_text()
        # A full container ID must be bounded to avoid prefix collisions.
        if not re.search(r"(?<![0-9a-f])" + re.escape(container_id) + r"(?![0-9a-f])", cgroup):
            return None
        status = Path(f"/proc/{pid}/status").read_text()
        match = re.search(r"^NSpid:\s+([\d\s]+)$", status, re.MULTILINE)
        return int(match.group(1).split()[-1]) if match else None
    except (OSError, ValueError):
        return None


def poll(containers: dict[str, tuple[str, float]], log_path: Path,
         sample: bool) -> None:
    processes = _processes()
    utilization = None
    if sample:
        try:
            utilization = _utilization()
        except (OSError, subprocess.CalledProcessError, ValueError):
            _log(log_path, event="utilization-unavailable")
    for name, (container_id, cap_gib) in containers.items():
        members = []
        for pid, memory_mib in processes:
            nspid = _container_pid(pid, container_id)
            if nspid is not None:
                members.append((memory_mib, pid, nspid))
        total = sum(item[0] for item in members)
        if sample:
            # Missing process readings are unknown, not zero utilization.
            readings = [utilization.get(pid) for _, pid, _ in members] if utilization is not None else []
            sm_percent = (sum(readings) if readings and all(value is not None for value in readings)
                          else 0 if utilization is not None and not members else None)
            _log(log_path, event="sample", container=name, memory_mib=total,
                 sm_utilization_percent=sm_percent)
        if total > cap_gib * 1024 and members:
            memory_mib, pid, nspid = max(members)
            # Recheck identity immediately before signalling; processes can disappear.
            if _container_pid(pid, container_id) != nspid:
                continue
            # Linux protects a PID namespace's init from signals sent by its
            # own namespace. docker exec kill can exit 0 without killing it.
            if nspid == 1:
                _log(log_path, event="kill-failed", container=name, pid=pid,
                     memory_mib=total, cap_gib=cap_gib, reason="namespace-init")
                continue
            try:
                _run("docker", "exec", "-u", str(_process_uid(pid)), name, "kill", "-9", str(nspid))
            except subprocess.CalledProcessError:
                _log(log_path, event="kill-failed", container=name, pid=pid,
                     memory_mib=total, cap_gib=cap_gib)
            else:
                _log(log_path, event="violation", container=name, pid=pid,
                     process_memory_mib=memory_mib, memory_mib=total, cap_gib=cap_gib)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--container", action="append", default=[], metavar="NAME:CAP_GIB")
    parser.add_argument("--sandbox-json", type=Path, help="state_dir/sandbox.json written by infra.sandbox.create")
    args = parser.parse_args()
    if args.sandbox_json:
        args.container.append(json.loads(args.sandbox_json.read_text())["gpu_watchdog_arg"])
    if not args.container:
        parser.error("--container or --sandbox-json required")
    containers = {}
    for value in args.container:
        try:
            name, cap = value.rsplit(":", 1)
            cap_gib = float(cap)
            if not name.startswith("wsp-") or not 0 < cap_gib < float("inf") or name in containers:
                raise ValueError
            container_id = _run("docker", "inspect", "--format", "{{.Id}}", name).strip()
            if not re.fullmatch(r"[0-9a-f]{64}", container_id):
                raise ValueError
            containers[name] = (container_id, cap_gib)
        except (ValueError, subprocess.CalledProcessError):
            parser.error(f"invalid or unavailable container: {value}")
    args.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    log_path = args.state_dir / "gpu-watchdog.jsonl"
    next_sample = 0.0
    while True:
        now = time.monotonic()
        sample = now >= next_sample
        try:
            poll(containers, log_path, sample)
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            _log(log_path, event="poll-error", error=type(exc).__name__)
        if sample:
            next_sample = now + 30
        time.sleep(5)


if __name__ == "__main__":
    main()
