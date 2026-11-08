"""Per-run workspace watcher (spec section 4, "Workspace watcher").

    python -m infra.watcher --workspace W --corpus C --state-dir S --control-dir D [--interval 120]

Scans new/changed regular files in the workspace (incremental: mtime/size/inode cache).
Classification per image (including images carved from blobs and found inside bounded
archives, reusing the proxy's scanner and limits):

  stop   raw/archive/normalized SHA-256 of an MFXR image that is not explained as a pool
         image; pHash Hamming <= 2 to a *test-split* image; text/binary file with >= 3
         distinct original MFXR basenames.
  alert  pHash Hamming 3..6 to a test-split image; unscannable/over-limit content.
  info   `pool-derivative`: matches only pool images (the pool is mounted on purpose).

A stop finding writes D/STOP_REQUEST.json {reason, file, rule, time}. Everything is also
logged to S/watcher.jsonl. Logs never contain corpus hashes, basenames or file contents.
SIGUSR1 triggers an immediate scan. Host-only process; control/state dirs must not be mounted
into the agent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import stat
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from infra.proxy import wsp_content as wc

STOP_DIST = 2
ALERT_DIST = 6
POOL_DIST = 6
STOP_FILE = "STOP_REQUEST.json"
DEFAULT_MAX_FILE = 2 * wc.GIB


class _Digests:
    """Container whose membership test records the digest instead of blocking."""

    def __init__(self, obs: "_Obs", kind: str, known: set[str], blocking: bool = False):
        self.obs, self.kind, self.known, self.blocking = obs, kind, known, blocking

    def __contains__(self, digest: str) -> bool:
        hit = digest in self.known
        self.obs.event(self.kind, hit)
        return hit and self.blocking

    def __bool__(self) -> bool:
        return bool(self.known)

    def __iter__(self):
        return iter(self.known)


class _Obs:
    """Ordered observations made by the scanner for one file."""

    def __init__(self):
        self.data: list[dict] = []
        self.archive_hit = False

    def event(self, kind: str, hit: bool):
        # wc.scan() tests every datum (file, archive member, carved chunk, base64 payload)
        # against the raw hashes first; a decodable image then tests the normalized hash and
        # pHash. So each "raw" event opens a datum and later events belong to it.
        if kind == "raw":
            self.data.append({"exact": hit, "phash": None})
        elif kind == "norm" and hit and self.data:
            self.data[-1]["exact"] = True
        elif kind == "archive" and hit:
            self.archive_hit = True

    def phash(self, test: int, pool: int):
        if self.data:
            self.data[-1]["phash"] = (test, pool)


class _WatchCorpus(wc.Corpus):
    """Corpus view for wc.scan that records matches; only the archive hash and basenames block."""

    def __init__(self, base: wc.Corpus, obs: _Obs):
        self.base, self.obs = base, obs
        self.test = np.array(base.phash_test, dtype=np.uint64)
        self.pool = np.array(base.phash_pool, dtype=np.uint64)
        self.basenames = base.basenames
        self.normalized = _Digests(obs, "norm", base.normalized)
        self.hashes_sha = _Combined(obs, base)

    def min_phash_distance(self, value: int) -> int:
        self.obs.phash(_min_dist(self.test, value), _min_dist(self.pool, value))
        return 64  # never block inside the scanner; we classify afterwards


class _Combined:
    """hashes_sha: records raw/archive membership; archive hash blocks via the scanner."""

    def __init__(self, obs: _Obs, base: wc.Corpus):
        self.obs, self.base = obs, base

    def __contains__(self, digest: str) -> bool:
        self.obs.event("raw", digest in self.base.raw)
        if digest in self.base.archive:
            self.obs.event("archive", True)
            return True
        return False


def _min_dist(values: np.ndarray, value: int) -> int:
    if not len(values):
        return 64
    return int(np.bitwise_count(values ^ np.uint64(value)).min())


def classify(obs: _Obs) -> tuple[str, str] | None:
    """Return (level, rule) for the most severe finding, or None when clean."""
    if obs.archive_hit:
        return "stop", "sha256-archive"
    worst: tuple[str, str] | None = None
    rank = {"stop": 3, "alert": 2, "info": 1}

    def note(level, rule):
        nonlocal worst
        if worst is None or rank[level] > rank[worst[0]]:
            worst = (level, rule)

    for d in obs.data:
        ph = d["phash"]
        if ph is not None:
            dt, dp = ph
            if dt <= STOP_DIST:
                note("stop", "phash-test")
                continue
            if d["exact"]:
                # Exact MFXR bytes/pixels: only acceptable when the image is a pool image.
                if dp <= STOP_DIST:
                    note("info", "pool-derivative")
                else:
                    note("stop", "sha256")
            elif dt <= ALERT_DIST:
                note("alert", "phash-test-near")
            elif dp <= POOL_DIST:
                note("info", "pool-derivative")
        elif d["exact"]:
            note("stop", "sha256")  # exact match on non-image bytes (e.g. an archive/blob of MFXR)
    return worst


@dataclass
class Watcher:
    workspace: Path
    corpus: wc.Corpus
    state_dir: Path
    control_dir: Path
    run_id: str | None = None
    limits: wc.Limits = field(default_factory=wc.Limits)
    max_file: int = DEFAULT_MAX_FILE

    def __post_init__(self):
        self.workspace = Path(self.workspace)
        self.state_dir = Path(self.state_dir)
        self.control_dir = Path(self.control_dir)
        for d in (self.state_dir, self.control_dir):
            d.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.cache: dict[str, tuple] = {}  # relpath -> (sig, level, rule)
        self.log_path = self.state_dir / "watcher.jsonl"
        self.stops: list[dict] = []

    # ------------------------------------------------------------ logging
    def _log(self, **event):
        event["time"] = datetime.now(timezone.utc).isoformat()
        if self.run_id:
            event["run_id"] = self.run_id
        fd = os.open(self.log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")

    def _stop(self, rel: str, rule: str):
        rec = {"reason": f"workspace file matched protected-data rule {rule}", "file": rel, "rule": rule,
               "time": datetime.now(timezone.utc).isoformat()}
        self.stops.append(rec)
        tmp = self.control_dir / (STOP_FILE + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(rec, f)
        os.replace(tmp, self.control_dir / STOP_FILE)

    # ------------------------------------------------------------ scanning
    def _files(self):
        for root, dirs, files in os.walk(self.workspace, followlinks=False):
            for name in files:
                p = Path(root) / name
                try:
                    st = p.lstat()
                except OSError:
                    continue
                if stat.S_ISREG(st.st_mode):  # symlinks/devices/fifos are never followed or read
                    yield p, st

    def scan_file(self, path: Path, size: int) -> tuple[str, str] | None:
        if size > self.max_file:
            return "alert", "unscannable-size"
        with open(path, "rb") as f:
            data = f.read(self.max_file + 1)
        obs = _Obs()
        wcorp = _WatchCorpus(self.corpus, obs)
        try:
            wc.scan(data, wcorp, wc.State(self.limits))
        except wc.Blocked as e:
            if e.rule == "basenames":
                return "stop", "basenames"
            result = classify(obs)
            if result and result[0] == "stop":
                return result
            return "alert", "unscannable-" + e.rule
        except Exception:
            return "alert", "unscannable-error"
        return classify(obs)

    def scan_once(self) -> list[dict]:
        """One incremental pass; returns the new findings (dicts without file contents)."""
        seen, findings = set(), []
        for path, st in self._files():
            rel = str(path.relative_to(self.workspace))
            seen.add(rel)
            sig = (st.st_mtime_ns, st.st_size, st.st_ino)
            cached = self.cache.get(rel)
            if cached and cached[0] == sig:
                continue
            try:
                result = self.scan_file(path, st.st_size)
                st2 = path.lstat()
            except OSError:
                continue  # vanished/unreadable: retried next pass (not cached)
            if (st2.st_mtime_ns, st2.st_size, st2.st_ino) != sig:
                continue  # modified while reading; rescan next pass
            self.cache[rel] = (sig, *(result or (None, None)))
            if result is None:
                continue
            level, rule = result
            self._log(event="finding", level=level, rule=rule, file=rel, size=st.st_size)
            findings.append({"level": level, "rule": rule, "file": rel})
            if level == "stop":
                self._stop(rel, rule)
        for gone in set(self.cache) - seen:
            del self.cache[gone]
        self._log(event="scan", files=len(seen), new_findings=len(findings))
        return findings

    def run(self, interval: float):
        wake = {"now": False}
        signal.signal(signal.SIGUSR1, lambda *_: wake.__setitem__("now", True))
        self._log(event="start", interval=interval)
        while True:
            try:
                self.scan_once()
            except Exception as exc:  # keep watching; never log exception text (may contain paths/data)
                self._log(event="scan-error", error=type(exc).__name__)
            end = time.monotonic() + interval
            while time.monotonic() < end and not wake["now"]:
                time.sleep(0.5)
            wake["now"] = False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--state-dir", type=Path, required=True)
    ap.add_argument("--control-dir", type=Path, required=True)
    ap.add_argument("--interval", type=float, default=120)
    ap.add_argument("--run-id")
    ap.add_argument("--once", action="store_true", help="scan once, exit 3 if a stop finding was made")
    a = ap.parse_args(argv)
    if not a.workspace.is_dir():
        ap.error("workspace is not a directory")
    try:
        corpus = wc.Corpus.load(a.corpus)
    except Exception as exc:
        print(f"cannot load corpus: {type(exc).__name__}", file=sys.stderr)
        return 2
    w = Watcher(a.workspace, corpus, a.state_dir, a.control_dir, a.run_id)
    if a.once:
        w.scan_once()
        return 3 if w.stops else 0
    w.run(a.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
