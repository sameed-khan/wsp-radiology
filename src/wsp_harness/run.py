"""Run initialization and a small, continuously draining Pi RPC driver."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
import uuid

from .config import digest, load_inputs, pi_argv, render
from .evidence import sha256

REPO = Path(__file__).resolve().parents[2]
IMAGE = 'ubuntu:24.04'
# Exact host variables passed to Pi: no PI_* markers, no API keys. Provider
# credentials come from Pi's own auth store under HOME. CA/proxy variables are
# needed for TLS-inspecting networks.
HOST_ENV = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TERM', 'NODE_EXTRA_CA_CERTS', 'SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE',
            'HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'no_proxy')


def utc(dt: datetime) -> str:
    return dt.isoformat().replace('+00:00', 'Z')


def create_run(root: Path, arm: str, k: int, labels_dir: Path, pool_dir: Path,
               hours: float, test_model: bool = False, image: str = IMAGE) -> Path:
    root, labels_dir, pool_dir = map(lambda p: Path(p).resolve(), (root, labels_dir, pool_dir))
    if not math.isfinite(hours) or hours <= 0:
        raise ValueError('hours must be positive and finite')
    if not pool_dir.is_dir() or not labels_dir.is_dir():
        raise ValueError('pool and labels must be directories')
    if arm.upper() == 'R':
        import csv
        with (labels_dir / 'labels.csv').open(newline='', encoding='utf-8-sig') as f:
            rows = list(csv.reader(f))
        if rows != [['image', 'patient', 'label']] or k != 0:
            raise ValueError('arm R requires k=0 and a header-only labels.csv')
        if {p.name for p in labels_dir.iterdir()} != {'labels.csv'}:
            raise ValueError('arm R labels directory must contain only labels.csv')
    labels_hash = sha256(labels_dir / 'labels.csv')
    inputs = load_inputs(root, arm, allow_test_model=test_model)
    image_id = subprocess.check_output(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'], text=True).strip()
    revision = subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip()
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=hours)
    run_id = now.strftime('%Y%m%dt%H%M%S') + '-' + uuid.uuid4().hex[:12]
    run = root / 'runs' / run_id
    run.mkdir(parents=True, mode=0o700)
    for name in ('recorder/sessions', 'recorder/subagents', 'workspace/output', 'workspace/home', 'snapshots', 'state', 'control'):
        (run / name).mkdir(parents=True, mode=0o700)
    # The agent's numeric uid is normally the host user's uid; allow the
    # configured identity to write even on installations with another host uid.
    for name in ('workspace', 'workspace/output', 'workspace/home'):
        (run / name).chmod(0o777)
    values = {'arm': arm.upper(), 'k': k, 'start_utc': utc(now), 'deadline_utc': utc(deadline),
              'now_utc': utc(now), 'remaining': str(timedelta(hours=hours)),
              'weight_sentence': inputs.weight_sentence, 'n_pool': sum(p.is_file() for p in pool_dir.iterdir())}
    prompt = render(inputs.launch_template, values)
    extensions = {p.name: sha256(p) for p in sorted((REPO / 'harness/pi-ext').iterdir()) if p.is_file()}
    launch = {'run_id': run_id, 'arm': arm.upper(), 'k': k, 'git_revision': revision,
              'input_hashes': inputs.hashes, 'extension_hashes': extensions,
              'model': inputs.model, 'subagent_model': 'anthropic/claude-haiku-5-5',
              'labels_sha256': labels_hash, 'labels_dir': str(labels_dir), 'pool_dir': str(pool_dir),
              'start_utc': utc(now), 'deadline_utc': utc(deadline), 'deadline_epoch': deadline.timestamp(),
              'launch_prompt': prompt, 'launch_prompt_sha256': digest(prompt.encode()),
              'n_pool': values['n_pool'], 'image': image, 'image_id': image_id, 'test_model': test_model}
    (run / 'launch.json').write_text(json.dumps(launch, indent=2) + '\n')
    (run / 'interventions.jsonl').touch(mode=0o600)
    (run / 'workspace/TASK.md').write_text(prompt)
    # Ubuntu's image provides python3 only; expose the conventional command in
    # its existing user-local PATH without modifying the read-only image.
    local_bin = run / 'workspace/home/.local/bin'
    local_bin.mkdir(parents=True, exist_ok=True)
    (local_bin / 'python').symlink_to('/usr/bin/python3')
    toolkit = root / 'toolkit/TOOLKIT.md'
    if not toolkit.is_file():
        toolkit = Path('/home/skhanxx8/projects/wsp-radiology/toolkit/TOOLKIT.md')
    if toolkit.is_file():
        shutil.copyfile(toolkit, run / 'workspace/TOOLKIT.md')
    else:
        result = subprocess.run(['docker', 'run', '--rm', '--name', f'wsp-seed-{run_id}', '--network', 'none', '--entrypoint', 'cat',
                                 image, '/opt/wsp-toolkit/TOOLKIT.md'], capture_output=True)
        if result.returncode == 0:
            (run / 'workspace/TOOLKIT.md').write_bytes(result.stdout)
    return run


class RpcDriver:
    """RPC stdout is recorded byte-for-byte; timestamps are in a parallel JSONL."""
    def __init__(self, run: Path, inputs, container: str, repo: Path = REPO, extra_args=()):
        self.run = Path(run).resolve()
        launch = json.loads((self.run / 'launch.json').read_text())
        env = {key: os.environ[key] for key in HOST_ENV if key in os.environ}
        env.update(WSP_CONTAINER=container, WSP_EXEC_USER='1004:1004',
                   WSP_RECORDER_DIR=str(self.run / 'recorder'),
                   WSP_DEADLINE_EPOCH=str(launch['deadline_epoch']))
        self.process = subprocess.Popen([*pi_argv(inputs, repo, self.run / 'recorder'), *extra_args],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=(self.run / 'recorder/pi-stderr.log').open('ab'),
                                        env=env, cwd=repo, start_new_session=True)
        self.events = queue.Queue()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        try:
            with (self.run / 'recorder/rpc-events.jsonl').open('ab', buffering=0) as log, \
                 (self.run / 'recorder/rpc-receive-times.jsonl').open('a', buffering=1) as times:
                for line in self.process.stdout:
                    log.write(line)
                    times.write(json.dumps({'received_utc': utc(datetime.now(timezone.utc))}) + '\n')
                    try:
                        self.events.put(json.loads(line))
                    except (ValueError, UnicodeError) as exc:
                        self.events.put(exc)
        finally:
            self.events.put(EOFError('Pi stdout closed'))

    def send(self, command: dict):
        self.process.stdin.write(json.dumps(command).encode() + b'\n')
        self.process.stdin.flush()

    def prompt(self, message: str):
        self.send({'id': uuid.uuid4().hex, 'type': 'prompt', 'message': message})

    def wait_idle(self, timeout: float):
        until = time.monotonic() + timeout
        while True:
            try:
                event = self.events.get(timeout=max(0, until - time.monotonic()))
            except queue.Empty:
                raise TimeoutError('Pi did not settle before the timeout') from None
            if isinstance(event, Exception):
                raise event
            if event.get('type') == 'response' and event.get('success') is False:
                raise RuntimeError(event.get('error', 'RPC command failed'))
            if event.get('type') == 'agent_settled' or (event.get('type') == 'response' and event.get('command') == 'prompt' and event.get('data', {}).get('disposition') == 'handled'):
                return event

    def close(self):
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.thread.join(timeout=5)
