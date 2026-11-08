#!/usr/bin/env python3
"""Build the agent-facing copy of the anonymized pool without ordering side channels.

The prepared pool was written in archive order (class by class), so file mtimes,
ctimes and inode numbers of `data/pool` reveal the class boundary. This script
copies the pool files (content and names unchanged) in a cryptographically random
order into a fresh directory, sets every atime/mtime to one fixed timestamp, and
verifies content hashes. The result is the only pool directory that may be
mounted into F/G/R agent sandboxes. Prints counts only; never reads labels.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = 1767225600  # 2026-01-01T00:00:00Z


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    source = (ROOT / "data/pool").resolve(strict=True)
    base = ROOT / "data/agent-pool"
    base.mkdir(mode=0o700, exist_ok=True)
    os.chmod(base, 0o700)
    dest = base / f"{source.parent.parent.name}-sanitized-{secrets.token_hex(4)}"
    dest.mkdir(mode=0o700)
    names = sorted(p.name for p in source.iterdir() if p.is_file())
    order = names[:]
    secrets.SystemRandom().shuffle(order)
    for name in order:
        shutil.copyfile(source / name, dest / name)
        os.chmod(dest / name, 0o600)
    for name in names:
        os.utime(dest / name, (FIXED_TIME, FIXED_TIME))
    os.utime(dest, (FIXED_TIME, FIXED_TIME))
    mismatched = [n for n in names if sha256(source / n) != sha256(dest / n)]
    if mismatched or sorted(p.name for p in dest.iterdir()) != names:
        print(json.dumps({"ok": False, "mismatched": len(mismatched)}))
        return 1
    mtimes = {(dest / n).stat().st_mtime_ns for n in names}
    current = base / "current"
    tmp = base / f".current-{secrets.token_hex(4)}"
    os.symlink(dest.name, tmp)
    os.replace(tmp, current)
    print(json.dumps({"ok": True, "files": len(names), "dest": str(dest),
                      "distinct_mtimes": len(mtimes), "copy_order": "secrets.SystemRandom shuffle"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
