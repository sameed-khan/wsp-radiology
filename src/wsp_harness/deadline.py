"""Host-owned, append-only deadline extension accounting."""
import fcntl
import json
import math
import os
from pathlib import Path


def append(run: Path, record: dict) -> None:
    seconds = record['seconds']
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('extension seconds must be positive and finite')
    path = run / 'state/deadline-extensions.jsonl'
    with path.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(record, ensure_ascii=True) + '\n')
        f.flush()
        os.fsync(f.fileno())


def total(run: Path) -> float:
    path = run / 'state/deadline-extensions.jsonl'
    try:
        with path.open() as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            records = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return 0.0
    values = [r['seconds'] for r in records]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('invalid deadline extension')
    result = math.fsum(values)
    if not math.isfinite(result):
        raise ValueError('deadline extensions overflow')
    return result
