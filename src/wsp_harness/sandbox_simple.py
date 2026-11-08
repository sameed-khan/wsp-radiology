"""Offline disposable sandbox for tests, not the production networked sandbox."""
from pathlib import Path
import json
import subprocess


def create(run: Path) -> str:
    run = Path(run).resolve()
    launch = json.loads((run / 'launch.json').read_text())
    name = 'wsp-agent-' + launch['run_id']
    mounts = [(run / 'workspace', '/workspace', False),
              (Path(launch['pool_dir']), '/inputs/pool', True),
              (Path(launch['labels_dir']), '/inputs/labels', True)]
    args = ['docker', 'run', '-d', '--init', '--name', name, '--hostname', name,
            '--network', 'none', '--user', '1004:1004', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev',
            '--env', 'HOME=/workspace/home', '-w', '/workspace']
    for src, dst, readonly in mounts:
        args += ['--mount', f'type=bind,src={src},dst={dst}' + (',readonly' if readonly else '')]
    subprocess.run([*args, launch['image_id'], 'sleep', 'infinity'], check=True, capture_output=True)
    return name


def destroy(container: str) -> None:
    if not container.startswith('wsp-agent-'):
        raise ValueError('refusing to remove non-agent container')
    subprocess.run(['docker', 'rm', '-f', container], check=True, capture_output=True)
