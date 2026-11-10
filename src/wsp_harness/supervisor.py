"""Trusted run lifecycle loop: continuation, retry, snapshots, deadline freeze.

One Supervisor instance drives one run to a frozen state. It never gives the
agent control over timing: all decisions use the host clock and host-side files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
import traceback
import uuid

from . import deadline, evidence, sandbox_simple
from .config import load_inputs, render
from .run import RpcDriver, utc


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_rate_limit(error: object) -> bool:
    text = str(error).lower()
    return any(term in text for term in ('429', 'rate_limit_error', 'rate limit', 'usage limit', 'overloaded', '529'))


def _remaining(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return str(timedelta(seconds=seconds))


class Supervisor:
    def __init__(self, run: Path, *, backend=sandbox_simple, continue_after: float = 300.0,
                 snapshot_interval: float = 3600.0, status_interval: float = 30.0,
                 retry_base: float = 1.0, retry_cap: float = 900.0, tick: float = 1.0):
        self.run = Path(run).resolve()
        self.launch = json.loads((self.run / 'launch.json').read_text())
        self.root = self.run.parent.parent
        self.inputs = load_inputs(self.root, self.launch['arm'], allow_test_model=self.launch['test_model'])
        if self.inputs.hashes != self.launch['input_hashes']:
            raise RuntimeError('preregistered inputs changed since launch.json was written')
        self.backend = backend
        self.continue_after, self.snapshot_interval = continue_after, snapshot_interval
        self.status_interval, self.retry_base, self.retry_cap, self.tick = status_interval, retry_base, retry_cap, tick
        self.original_deadline = float(self.launch['deadline_epoch'])
        self.deadline = self.original_deadline
        self.extensions_seconds = 0.0
        self.outage_start: float | None = None
        self.refresh_deadline()
        self.start = datetime.fromisoformat(self.launch['start_utc'].replace('Z', '+00:00')).timestamp()
        self.container: str | None = None
        self.driver: RpcDriver | None = None
        self.phase = 'starting'
        self.reason: str | None = None
        self.running = False  # agent has an active run
        self.idle_since: float | None = None
        self.last_event: float | None = None
        self.turns = self.tool_calls = self.continuations = self.retries = self.restarts = 0
        self.snapshots = 0
        self.last_error: str | None = None
        self.failures = 0  # consecutive failures driving backoff
        self.retry_at: float | None = None
        self.retry_mode: str | None = None
        self.last_stop: str | None = None
        self.stop_signal = False
        self.log_file = (self.run / 'recorder/supervisor.log').open('a', buffering=1)
        self.final_snapshot: str | None = None
        self.messages_delivered = 0

    def refresh_deadline(self) -> None:
        seconds = deadline.total(self.run)
        self.extensions_seconds = seconds
        self.deadline = self.original_deadline + seconds
        state = {'deadline_epoch': self.deadline, 'deadline_utc': utc(datetime.fromtimestamp(self.deadline, timezone.utc)),
                 'extensions_seconds': seconds}
        path = self.run / 'state/deadline.json'
        if not path.exists() or json.loads(path.read_text()) != state:
            tmp = path.with_name(f'.deadline.{os.getpid()}.{uuid.uuid4().hex}.tmp')
            tmp.write_text(json.dumps(state) + '\n')
            os.replace(tmp, path)

    def rate_failure(self, error: object, now: float) -> None:
        if self.outage_start is None and is_rate_limit(error):
            self.outage_start = now
            (self.run / 'state/rate-limit-outage.json').write_text(json.dumps({'start_epoch': now}) + '\n')

    def rate_recovered(self, now: float) -> None:
        if self.outage_start is None:
            return
        start = self.outage_start
        seconds = max(now - start, 0.000001)
        record = {'time_utc': utc(datetime.fromtimestamp(now, timezone.utc)), 'seconds': seconds,
                  'reason': 'rate-limit', 'kind': 'auto',
                  'outage_start_utc': utc(datetime.fromtimestamp(start, timezone.utc)),
                  'outage_end_utc': utc(datetime.fromtimestamp(now, timezone.utc))}
        deadline.append(self.run, record)
        self.outage_start = None
        self.refresh_deadline()
        (self.run / 'state/rate-limit-outage.json').unlink(missing_ok=True)
        self.intervention('rate-limit-extension', **record)
        text = self.inputs.extension_template.format(lost=_remaining(seconds), deadline_utc=utc(datetime.fromtimestamp(self.deadline, timezone.utc)),
                               remaining=_remaining(self.deadline - now)).strip()
        if self.running:
            self.driver.send({'id': uuid.uuid4().hex, 'type': 'steer', 'message': text})
            mode = 'steer'
        else:
            self.send_prompt(text)
            mode = 'prompt'
        self.messages_delivered += 1
        self.intervention('rate-limit-notice-delivered', mode=mode, message=text)

    # ---- logging / state ----
    def log(self, message: str) -> None:
        self.log_file.write(f'{utc(_now())} {message}\n')

    def intervention(self, event: str, **fields) -> None:
        record = {'utc': utc(_now()), 'kind': 'auto', 'event': event, **fields}
        with (self.run / 'interventions.jsonl').open('a') as f:
            f.write(json.dumps(record) + '\n')
        self.log(f'{event} {fields}')

    def write_status(self) -> None:
        now = time.time()
        status = {
            'run_id': self.launch['run_id'], 'pid': os.getpid(), 'phase': self.phase, 'reason': self.reason,
            'updated_utc': utc(_now()), 'start_utc': self.launch['start_utc'],
            'deadline_utc': utc(datetime.fromtimestamp(self.deadline, timezone.utc)),
            'original_deadline_utc': self.launch['deadline_utc'], 'extensions_seconds': self.extensions_seconds,
            'last_event_utc': utc(datetime.fromtimestamp(self.last_event, timezone.utc)) if self.last_event else None,
            'turns': self.turns, 'tool_calls': self.tool_calls, 'agent_running': self.running,
            'idle_seconds': round(now - self.idle_since, 1) if self.idle_since else 0,
            'continuations': self.continuations, 'retries': self.retries, 'restarts': self.restarts,
            'snapshots': self.snapshots, 'last_error': self.last_error, 'container': self.container,
            'final_snapshot': self.final_snapshot, 'messages_delivered': self.messages_delivered,
            'backend': getattr(self.backend, '__name__', str(self.backend)).rsplit('.', 1)[-1],
        }
        tmp = self.run / 'state/.status.json.tmp'
        tmp.write_text(json.dumps(status, indent=2) + '\n')
        os.replace(tmp, self.run / 'state/status.json')

    # ---- pi process ----
    def start_pi(self, resume: bool) -> None:
        extra = []
        if resume:
            sessions = sorted((self.run / 'recorder/sessions').glob('*.jsonl'), key=lambda p: p.stat().st_mtime)
            if sessions:
                extra = ['--session', str(sessions[-1])]
        self.driver = RpcDriver(self.run, self.inputs, self.container, extra_args=extra)
        self.running = False

    def send_prompt(self, text: str) -> None:
        self.driver.prompt(text)
        self.running = True
        self.idle_since = None

    def continuation_text(self) -> str:
        now = time.time()
        values = {'arm': self.launch['arm'], 'k': self.launch['k'], 'start_utc': self.launch['start_utc'],
                  'deadline_utc': utc(datetime.fromtimestamp(self.deadline, timezone.utc)), 'now_utc': utc(_now()),
                  'remaining': _remaining(self.deadline - now), 'weight_sentence': self.inputs.weight_sentence,
                  'n_pool': self.launch.get('n_pool', 0)}
        return render(self.inputs.continuation_template, values)

    def kill_processes(self) -> None:
        """Abort via RPC, then kill pi's process group and any recorded subagent children."""
        d = self.driver
        if d and d.process.poll() is None:
            try:
                d.send({'id': uuid.uuid4().hex, 'type': 'abort'})
                time.sleep(1.0)
            except OSError:
                pass
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(d.process.pid, sig)
                except ProcessLookupError:
                    pass
                try:
                    d.process.wait(timeout=5)
                    break
                except subprocess.TimeoutExpired:
                    continue
        # Subagent children are detached pi processes carrying our recorder dir in their environment.
        marker = f'WSP_RECORDER_DIR={self.run / "recorder"}'.encode()
        for pid_dir in Path('/proc').iterdir():
            if not pid_dir.name.isdigit() or int(pid_dir.name) == os.getpid():
                continue
            try:
                if marker in (pid_dir / 'environ').read_bytes().split(b'\0'):
                    os.kill(int(pid_dir.name), signal.SIGKILL)
                    self.log(f'killed leftover process {pid_dir.name}')
            except (OSError, ValueError):
                continue
        if d:
            try:
                d.close()
            except Exception:
                pass

    # ---- event handling ----
    def handle_event(self, event: dict) -> None:
        self.last_event = time.time()
        kind = event.get('type')
        if kind == 'auto_retry_start':
            self.rate_failure(event.get('errorMessage', event.get('error', '')), self.last_event)
        elif kind == 'message_update':
            msg = event.get('message') or {}
            update = event.get('assistantMessageEvent') or {}
            if msg.get('role') == 'assistant' and update.get('type') in ('text_delta', 'thinking_delta', 'toolcall_delta'):
                self.rate_recovered(self.last_event)
        if kind == 'turn_start':
            self.turns += 1
        elif kind == 'tool_execution_end':
            self.tool_calls += 1
        elif kind == 'message_end':
            msg = event.get('message') or {}
            if msg.get('role') == 'assistant':
                self.last_stop = msg.get('stopReason')
                if self.last_stop == 'error':
                    self.last_error = str(msg.get('errorMessage', 'assistant error'))[:500]
                    self.rate_failure(self.last_error, self.last_event)
                elif self.last_stop not in ('aborted',):
                    self.rate_recovered(self.last_event)
        elif kind == 'auto_retry_end' and event.get('success') is False:
            self.last_error = str(event.get('finalError', 'retry failed'))[:500]
            self.rate_failure(self.last_error, self.last_event)
        elif kind == 'response' and event.get('command') == 'prompt':
            if event.get('success') is False:
                self.last_error = str(event.get('error'))[:500]
                self.rate_failure(self.last_error, self.last_event)
                self.schedule_retry('error')
            elif (event.get('data') or {}).get('disposition') == 'handled':
                self.running = False
                self.idle_since = self.idle_since or time.time()
        elif kind == 'agent_settled':
            self.running = False
            if event.get('aborted'):
                self.idle_since = time.time()
            elif self.last_stop == 'error':
                self.schedule_retry('error')
            else:
                self.failures = 0
                self.idle_since = time.time()
            self.last_stop = None

    def schedule_retry(self, mode: str) -> None:
        delay = min(self.retry_cap, self.retry_base * (2 ** self.failures))
        self.failures += 1
        self.running = False
        self.idle_since = None
        self.retry_mode = mode
        self.retry_at = time.time() + delay
        self.intervention('auto-retry-scheduled', mode=mode, delay_seconds=delay, error=self.last_error)

    def do_retry(self) -> None:
        mode, self.retry_mode, self.retry_at = self.retry_mode, None, None
        self.retries += 1
        self.intervention('auto-retry', mode=mode, attempt=self.retries, error=self.last_error)
        if mode == 'crash':
            self.restarts += 1
            try:
                self.driver.close()
            except Exception:
                pass
            self.start_pi(resume=True)
        self.send_prompt(self.continuation_text())

    # ---- lifecycle ----
    def final_exists(self) -> bool:
        return (self.run / 'workspace/output/FINAL').exists()

    def stop_request(self) -> str | None:
        path = self.run / 'control/STOP_REQUEST.json'
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return str(data.get('reason', 'stop-request'))
        except (ValueError, OSError):
            return 'stop-request (unparseable)'

    def deliver_messages(self) -> None:
        """Deliver control/messages/*.json (written by `wsp-harness intervene --kind message`)."""
        folder = self.run / 'control/messages'
        if not folder.is_dir():
            return
        for path in sorted(folder.glob('*.json')):
            done = folder / 'delivered'
            done.mkdir(exist_ok=True)
            target = done / path.name
            try:
                os.replace(path, target)  # claim first: never deliver twice
                text = str(json.loads(target.read_text())['message'])
            except (OSError, ValueError, KeyError) as exc:
                self.log(f'bad message file {path.name}: {exc}')
                continue
            try:
                if self.running:
                    self.driver.send({'id': uuid.uuid4().hex, 'type': 'steer', 'message': text})
                    mode = 'steer'
                else:
                    self.send_prompt(text)
                    mode = 'prompt'
            except OSError as exc:
                self.last_error = f'message delivery failed: {exc}'
                self.intervention('message-delivery-failed', file=path.name, error=str(exc))
                continue
            self.messages_delivered += 1
            self.intervention('message-delivered', file=path.name, mode=mode)

    def freeze(self, reason: str) -> None:
        self.phase, self.reason = 'freezing', reason
        self.write_status()
        errors = []
        self.log(f'freeze: {reason}')
        for step in (self.kill_processes,):
            try:
                step()
            except Exception as exc:
                errors.append(f'kill: {exc}')
        try:
            if self.container:
                self.backend.pause(self.container)
        except Exception as exc:
            errors.append(f'pause: {exc}')
        try:
            snap = evidence.snapshot(self.run / 'workspace', self.run / 'snapshots')
            self.snapshots += 1
            self.final_snapshot = snap.name
            (self.run / 'state/final-snapshot.json').write_text(json.dumps({'snapshot': snap.name, 'reason': reason}) + '\n')
        except Exception as exc:
            errors.append(f'snapshot: {exc}')
        try:
            if self.container:
                self.backend.destroy(self.container)
        except Exception as exc:
            errors.append(f'destroy: {exc}')
        try:
            stop = getattr(self.backend, 'stop_helpers', None)
            if stop:
                stop()
        except Exception as exc:
            errors.append(f'helpers: {exc}')
        if errors:
            self.last_error = '; '.join(errors)
            self.log(f'freeze errors: {self.last_error}')
        self.phase = 'frozen' if not errors else 'frozen-with-errors'
        self.write_status()

    def run_loop(self) -> str:
        next_snapshot = time.time() + self.snapshot_interval
        next_status = 0.0
        while True:
            now = time.time()
            self.refresh_deadline()
            if now >= next_status:
                self.write_status()
                next_status = now + self.status_interval
            if self.stop_signal:
                return 'signal'
            if now >= self.deadline and self.outage_start is None:
                return 'deadline'
            if (reason := self.stop_request()) is not None:
                return f'stop-request: {reason}'
            check = getattr(self.backend, 'check_helpers', None)
            if check:
                check(self.run, self.container, self.log)
            self.deliver_messages()
            if now >= next_snapshot:
                try:
                    evidence.snapshot(self.run / 'workspace', self.run / 'snapshots')
                    self.snapshots += 1
                    self.log('periodic snapshot')
                except Exception as exc:
                    self.log(f'periodic snapshot failed: {exc}')
                next_snapshot = time.time() + self.snapshot_interval
            try:
                event = self.driver.events.get(timeout=self.tick if self.outage_start is not None else min(self.tick, max(0.0, self.deadline - time.time())))
            except queue.Empty:
                event = None
            if isinstance(event, Exception):
                if isinstance(event, EOFError):
                    if self.final_exists():
                        return 'final'
                    self.last_error = f'pi exited with code {self.driver.process.poll()}'
                    self.schedule_retry('crash')
                else:
                    self.log(f'unparseable RPC line: {event}')
            elif event is not None:
                self.handle_event(event)
            now = time.time()
            if self.retry_at and now >= self.retry_at:
                self.do_retry()
            elif not self.running and self.retry_at is None and self.idle_since is not None:
                if self.final_exists():
                    return 'final'
                if now - self.idle_since >= self.continue_after:
                    self.continuations += 1
                    self.intervention('auto-continuation', n=self.continuations,
                                      idle_seconds=round(now - self.idle_since, 1))
                    self.send_prompt(self.continuation_text())
            self.phase = 'retrying' if self.retry_at else ('running' if self.running else 'idle')

    def run_all(self) -> str:
        def on_term(*_):
            self.stop_signal = True
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, on_term)
            signal.signal(signal.SIGINT, on_term)
        reason = 'supervisor-error'
        try:
            self.container = self.backend.create(self.run)
            start = getattr(self.backend, 'start_helpers', None)
            if start:
                start(self.run, self.container)
            self.write_status()
            self.start_pi(resume=False)
            self.send_prompt(self.launch['launch_prompt'])
            reason = self.run_loop()
        except BaseException as exc:
            self.last_error = f'{type(exc).__name__}: {exc}'
            self.log(traceback.format_exc())
        finally:
            self.freeze(reason)
        return reason


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog='python -m wsp_harness.supervisor')
    p.add_argument('--run', required=True)
    p.add_argument('--backend', default='simple', choices=['simple', 'infra'])
    p.add_argument('--continue-after', type=float, default=300.0)
    p.add_argument('--snapshot-interval', type=float, default=3600.0)
    p.add_argument('--status-interval', type=float, default=30.0)
    a = p.parse_args(argv)
    if a.backend == 'infra':
        from . import sandbox_infra as backend
    else:
        backend = sandbox_simple
    sup = Supervisor(Path(a.run), backend=backend, continue_after=a.continue_after, snapshot_interval=a.snapshot_interval,
                     status_interval=a.status_interval)
    (sup.run / 'state/supervisor.pid').write_text(str(os.getpid()))
    print(sup.run_all())
    return 0


if __name__ == '__main__':
    sys.exit(main())
