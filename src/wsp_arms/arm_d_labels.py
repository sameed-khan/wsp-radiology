"""Preregistered zero-shot pool annotation. Cache contains sensitive image-level outputs."""
from __future__ import annotations

import concurrent.futures
import fcntl
import hashlib
import json
import math
import os
import subprocess
import re
import tempfile
import time
from pathlib import Path

from . import core

MODEL = 'anthropic/claude-opus-5-5'
INFRA_RETRY_SECONDS = 3600
INFRA_ERRORS = {'CalledProcessError', 'TimeoutExpired', 'SubprocessError', 'OSError',
                'FileNotFoundError', 'PermissionError'}
# Pi can report API failures as successful process output rather than an exit error.
INFRA_TEXT = re.compile(r'\b429\b|rate[ -]limit|usage limit|usage.*limit reached|'
                        r'limit.*(?:reached|exceeded)|too many requests|'
                        r'overloaded|service unavailable', re.IGNORECASE)


def _legacy_infrastructure_failure(row):
    return row.get('p_monteggia') is None and row.get('error') in INFRA_ERRORS


def parse_response(text):
    """Accept exactly one JSON object, with only the preregistered numeric field."""
    obj = json.loads(text)
    if not isinstance(obj, dict) or set(obj) != {'p_monteggia'}:
        raise ValueError('expected exactly p_monteggia')
    p = obj['p_monteggia']
    if isinstance(p, bool) or not isinstance(p, int) or not math.isfinite(p) or not 0 <= p <= 100:
        raise ValueError('invalid probability')
    return float(p)


def run(root=None, *, limit=None, workers=6, retries=3, timeout=180):
    paths = core.Paths(Path(root)) if root else core.Paths.default()
    if workers < 1 or retries < 1 or timeout <= 0 or (limit is not None and limit < 1):
        raise ValueError('workers, retries, timeout and limit must be positive')
    prompt_path = paths.root / 'config/arm-d-prompt.md'
    prompt = prompt_path.read_text()
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    pool = paths.root / 'data/pool'
    images = sorted(pool.glob('*.png'))
    if not images:
        raise ValueError('pool contains no PNG images')
    if limit is not None:
        images = images[:limit]
    directory = paths.private / 'arm-d'
    core.private_mkdir(directory, paths.private)
    lock_path = directory / 'cache.lock'
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cache = directory / 'labels.jsonl'
        completed = {}
        if cache.exists():
            rows = []
            with cache.open() as f:
                for line in f:
                    row = json.loads(line)
                    if row['prompt_sha256'] != prompt_hash or row['model'] != MODEL:
                        raise ValueError('cache prompt/model mismatch')
                    rows.append(row)
            # Old versions persisted infrastructure errors as exclusions. Remove
            # those entries under the cache lock, before appending new results.
            if any(_legacy_infrastructure_failure(row) for row in rows):
                rows = [row for row in rows if not _legacy_infrastructure_failure(row)]
                tmp_name = None
                try:
                    with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False) as tmp:
                        tmp_name = tmp.name
                        for row in rows:
                            tmp.write(json.dumps(row, allow_nan=False) + '\n')
                        tmp.flush()
                        os.fsync(tmp.fileno())
                    os.replace(tmp_name, cache)
                finally:
                    if tmp_name and os.path.exists(tmp_name):
                        os.unlink(tmp_name)
            for row in rows:
                completed[row['image']] = row

        def query(image):
            command = ['pi', '-p', '--no-session', '--model', MODEL, '--thinking', 'low', '--no-tools',
                       '--no-extensions', '--no-skills', '--no-context-files', '--no-prompt-templates',
                       '@' + str(image), prompt]
            deadline = time.monotonic() + INFRA_RETRY_SECONDS
            validation_failures = 0
            attempts = 0
            infra_failures = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                attempts += 1
                try:
                    result = subprocess.run(command, capture_output=True, text=True,
                                            timeout=min(timeout, remaining), check=True)
                    if INFRA_TEXT.search(result.stdout + '\n' + result.stderr):
                        raise RuntimeError('infrastructure response')
                except (subprocess.SubprocessError, OSError, RuntimeError):
                    infra_failures += 1
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                    time.sleep(min(2 ** min(infra_failures - 1, 10), 60, remaining))
                    continue
                try:
                    p = parse_response(result.stdout.strip())
                    return {'image': image.name, 'image_sha256': core.sha256_file(image), 'prompt_sha256': prompt_hash,
                            'model': MODEL, 'p_monteggia': p, 'response': result.stdout, 'attempts': attempts}
                except ValueError as exc:
                    validation_failures += 1
                    if validation_failures >= retries:
                        return {'image': image.name, 'image_sha256': core.sha256_file(image),
                                'prompt_sha256': prompt_hash, 'model': MODEL, 'p_monteggia': None,
                                'attempts': attempts, 'error': type(exc).__name__}
        todo = []
        for image in images:
            prior = completed.get(image.name)
            if prior and prior['image_sha256'] != core.sha256_file(image):
                raise ValueError('cached image content changed')
            if prior is None:
                todo.append(image)
        fd = os.open(cache, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'a') as out, concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(query, image) for image in todo]
            for future in concurrent.futures.as_completed(futures):
                row = future.result()
                if row is None:
                    continue
                out.write(json.dumps(row, allow_nan=False) + '\n')
                out.flush()
                os.fsync(out.fileno())
                completed[row['image']] = row
        missing = sum(i.name not in completed for i in images)
        excluded = sum(completed[i.name]['p_monteggia'] is None for i in images if i.name in completed)
        return {'images': len(images), 'new': len(todo), 'failed': excluded + missing,
                'excluded': excluded, 'uncached': missing, 'cache': str(cache)}
