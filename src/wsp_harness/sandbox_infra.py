"""Production sandbox backend: adapter over lane L2's ``infra`` package.

``infra.sandbox`` and the helper modules are imported lazily so that the simple
backend and the test-suite do not need them. Settings that are not part of
launch.json (models/external dirs, image, hash corpus, GPU cap) are read from
``state/backend.json`` written by ``wsp-harness launch``.

API used (from l3-task.md):
  SandboxSpec(run_id, workspace, pool_dir, labels_dir, models_dir, external_dir, image, state_dir,
              hash_corpus, gpu_mem_cap_gib=11.0, cpus=10, memory="28g")
  create(spec) -> Sandbox(run_id, container, proxy, network); pause(sb); unpause(sb); destroy(sb)
  python -m infra.watcher --workspace W --corpus C --state-dir S --control-dir D
  python -m infra.gpu_watchdog --state-dir S --container NAME:CAP_GIB
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

_SANDBOXES: dict[str, object] = {}
_HELPERS: list[subprocess.Popen] = []


def _config(run: Path) -> dict:
    return json.loads((run / 'state/backend.json').read_text())


def _sandbox_module():
    return importlib.import_module('infra.sandbox')


def create(run: Path) -> str:
    run = Path(run).resolve()
    launch = json.loads((run / 'launch.json').read_text())
    cfg = _config(run)
    mod = _sandbox_module()
    (run / 'state/sandbox').mkdir(exist_ok=True)
    kwargs = dict(run_id=launch['run_id'], workspace=run / 'workspace', pool_dir=Path(launch['pool_dir']),
                  labels_dir=Path(launch['labels_dir']), models_dir=Path(cfg['models_dir']),
                  external_dir=Path(cfg['external_dir']), image=cfg['image'], state_dir=run / 'state/sandbox',
                  hash_corpus=Path(cfg['hash_corpus']))
    if cfg.get('gpu_mem_cap_gib') is not None:
        kwargs['gpu_mem_cap_gib'] = float(cfg['gpu_mem_cap_gib'])
    sb = mod.create(mod.SandboxSpec(**kwargs))
    _SANDBOXES[sb.container] = sb
    return sb.container


def pause(container: str) -> None:
    _sandbox_module().pause(_SANDBOXES[container])


def unpause(container: str) -> None:
    _sandbox_module().unpause(_SANDBOXES[container])


def destroy(container: str) -> None:
    sb = _SANDBOXES.pop(container, None)
    if sb is not None:
        _sandbox_module().destroy(sb)


def helper_argv(run: Path, container: str) -> list[list[str]]:
    run = Path(run).resolve()
    cfg = _config(run)
    py = sys.executable
    return [
        [py, '-m', 'infra.watcher', '--workspace', str(run / 'workspace'), '--corpus', str(cfg['hash_corpus']),
         '--state-dir', str(run / 'state/watcher'), '--control-dir', str(run / 'control')],
        [py, '-m', 'infra.gpu_watchdog', '--state-dir', str(run / 'state/gpu'),
         '--container', f"{container}:{cfg.get('gpu_mem_cap_gib', 11.0)}"],
    ]


def start_helpers(run: Path, container: str) -> None:
    run = Path(run).resolve()
    for name in ('watcher', 'gpu'):
        (run / 'state' / name).mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'LANG', 'PYTHONPATH')}
    for argv in helper_argv(run, container):
        log = (run / 'state' / f'{argv[2].split(".")[-1]}.log').open('ab')
        _HELPERS.append(subprocess.Popen(argv, stdout=log, stderr=log, stdin=subprocess.DEVNULL, env=env,
                                         cwd=Path(__file__).resolve().parents[2], start_new_session=True))


def stop_helpers() -> None:
    while _HELPERS:
        proc = _HELPERS.pop()
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
