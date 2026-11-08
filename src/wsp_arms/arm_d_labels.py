"""Preregistered zero-shot pool annotation. Cache contains sensitive image-level outputs."""
from __future__ import annotations

import concurrent.futures
import fcntl
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

from . import core

MODEL = 'anthropic/claude-opus-5-5'


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
            with cache.open() as f:
                for line in f:
                    row = json.loads(line)
                    if row['prompt_sha256'] != prompt_hash or row['model'] != MODEL:
                        raise ValueError('cache prompt/model mismatch')
                    completed[row['image']] = row
        def query(image):
            command = ['pi', '-p', '--no-session', '--model', MODEL, '--thinking', 'low', '--no-tools',
                       '--no-extensions', '--no-skills', '--no-context-files', '--no-prompt-templates',
                       '@' + str(image), prompt]
            error = None
            for attempt in range(1, retries + 1):
                try:
                    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=True)
                    p = parse_response(result.stdout.strip())
                    return {'image': image.name, 'image_sha256': core.sha256_file(image), 'prompt_sha256': prompt_hash,
                            'model': MODEL, 'p_monteggia': p, 'response': result.stdout, 'attempts': attempt}
                except (ValueError, subprocess.SubprocessError, OSError) as exc:
                    error = type(exc).__name__
            return {'image': image.name, 'image_sha256': core.sha256_file(image), 'prompt_sha256': prompt_hash,
                    'model': MODEL, 'p_monteggia': None, 'attempts': retries, 'error': error}
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
                out.write(json.dumps(row, allow_nan=False) + '\n')
                out.flush()
                os.fsync(out.fileno())
                completed[row['image']] = row
        failed = sum(completed[i.name]['p_monteggia'] is None for i in images)
        return {'images': len(images), 'new': len(todo), 'failed': failed, 'cache': str(cache)}
