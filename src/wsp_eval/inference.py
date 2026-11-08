"""Run frozen agent inference in a network-isolated Docker container."""
import json
import math
import os
import re
import subprocess
import time
import uuid
from pathlib import Path


def docker_args(image, name, workspace, images, output):
    def mount(source, target, readonly=False):
        source = str(Path(source).resolve(strict=True))
        if ',' in source: raise ValueError('commas in mount paths are unsupported')
        return f'type=bind,src={source},dst={target}' + (',readonly' if readonly else '')
    return ['docker', 'create', '--name', name, '--network', 'none', '--gpus', 'all',
            '--mount', mount(workspace, '/workspace', True),
            '--mount', mount(images, '/eval/images', True),
            '--mount', mount(output, '/eval/out'), image, 'python',
            '/workspace/output/model/predict.py', '--images', '/eval/images',
            '--out', '/eval/out/preds.csv']


def _gpu_usage(container_id):
    output = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,used_memory',
                                      '--format=csv,noheader,nounits'], text=True)
    total = 0
    for line in output.splitlines():
        pid, memory = line.split(',')
        try:
            cgroup = Path(f'/proc/{int(pid)}/cgroup').read_text()
        except FileNotFoundError:
            continue
        if re.search(r'(?<![0-9a-f])' + re.escape(container_id) + r'(?![0-9a-f])', cgroup):
            total += int(memory)
    return total


def infer(args):
    from .cli import private_dir, score
    out = private_dir(args.out)
    workspace = Path(args.workspace).resolve(strict=True)
    threshold_path = (workspace / 'output/model/threshold.json').resolve(strict=True)
    if not threshold_path.is_relative_to(workspace): raise ValueError('threshold escapes workspace')
    threshold = json.loads(threshold_path.read_text())['threshold']
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('invalid threshold')
    prediction_dir = out / 'inference-output'
    prediction_dir.mkdir(mode=0o700)
    os.chown(prediction_dir, 1004, 1004)
    name = 'wsp-eval-' + uuid.uuid4().hex
    command = docker_args(args.image, name, workspace, args.images, prediction_dir)
    cid = subprocess.check_output(command, text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{64}', cid): raise RuntimeError('invalid container id')
    try:
        subprocess.run(['docker', 'start', cid], check=True, capture_output=True)
        deadline = time.monotonic() + 10800
        while True:
            if time.monotonic() >= deadline: raise TimeoutError('inference exceeded three hours')
            if _gpu_usage(cid) > 11 * 1024: raise RuntimeError('GPU memory cap exceeded')
            state = subprocess.check_output(['docker', 'inspect', '--format', '{{.State.Running}} {{.State.ExitCode}}', cid], text=True).split()
            if state[0] == 'false':
                if state[1] != '0': raise RuntimeError('inference container failed')
                break
            time.sleep(5)
    finally:
        subprocess.run(['docker', 'rm', '-f', cid], check=False, capture_output=True)
    args.preds = prediction_dir / 'preds.csv'
    if args.preds.is_symlink() or not args.preds.is_file(): raise ValueError('predictor did not produce a regular CSV')
    args.threshold = threshold
    score(args)
