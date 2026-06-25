#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

TRANSIENT_MARKERS = [
    'stream disconnected',
    'response stream',
    'reconnect',
    'timeout',
    'connection reset',
    'broken pipe',
    'disk full',
    'no space left',
]


def utc_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def kill_process_tree(pid: int) -> None:
    if os.name == 'nt':
        subprocess.run(
            ['taskkill', '/PID', str(pid), '/T', '/F'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
        )
        return
    try:
        os.kill(pid, 9)
    except OSError:
        pass


def transient_suspected(*texts: str) -> bool:
    haystack = '\n'.join(texts).lower()
    return any(marker in haystack for marker in TRANSIENT_MARKERS)


def base_status(args: argparse.Namespace, command: list[str]) -> dict[str, Any]:
    return {
        'schema_version': '1.0',
        'generated_by': 'codex_exec_adapter.py',
        'workspace': str(Path(args.workspace).resolve()),
        'task_dir': str(Path(args.task_dir).resolve()),
        'prompt_file': str(Path(args.prompt_file).resolve()),
        'output_last_message': str(Path(args.output_last_message).resolve()),
        'codex_home': str(Path(args.codex_home).resolve()) if args.codex_home else os.environ.get('CODEX_HOME', ''),
        'sandbox': args.sandbox,
        'command': command,
        'started_at': '',
        'finished_at': '',
        'duration_seconds': None,
        'returncode': None,
        'status': 'dry_run' if args.dry_run else 'not_started',
        'stdout_log': str(Path(args.stdout_log).resolve()),
        'stderr_log': str(Path(args.stderr_log).resolve()),
        'stdout_bytes': 0,
        'stderr_bytes': 0,
        'output_last_message_exists': False,
        'error_summary': '',
        'transient_failure_suspected': False,
    }


def stream_reader(stream, log_path: Path, state: dict[str, Any], key: str, lock: threading.Lock) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('w', encoding='utf-8', errors='replace') as handle:
        while True:
            chunk = stream.readline()
            if chunk == '':
                break
            handle.write(chunk)
            handle.flush()
            with lock:
                state[key].append(chunk)
                state[f'{key}_bytes'] += len(chunk.encode('utf-8', errors='replace'))
                state['last_output_at'] = time.monotonic()


def build_command(args: argparse.Namespace) -> list[str]:
    codex = args.codex_command or resolve_codex_command() or 'codex'
    command = [
        codex,
        'exec',
        '--cd',
        str(Path(args.workspace).resolve()),
        '--sandbox',
        args.sandbox,
        '--output-last-message',
        str(Path(args.output_last_message).resolve()),
    ]
    if should_skip_git_repo_check(args):
        command.append('--skip-git-repo-check')
    for item in args.extra_codex_arg or []:
        command.append(str(item))
    command.append('-')
    return command


def resolve_codex_command() -> str:
    if sys.platform == 'win32':
        for name in ['codex.cmd', 'codex.exe', 'codex.bat']:
            found = shutil.which(name)
            if found:
                return found
    found = shutil.which('codex')
    if found:
        return found
    if sys.platform == 'win32':
        for name in ['codex.ps1', 'codex']:
            found = shutil.which(name)
            if found:
                return found
    return ''


def is_git_worktree(path: Path) -> bool:
    try:
        proc = subprocess.run(
            ['git', '-C', str(path), 'rev-parse', '--is-inside-work-tree'],
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=5,
        )
        return proc.returncode == 0 and proc.stdout.strip().lower() == 'true'
    except Exception:
        return False


def should_skip_git_repo_check(args: argparse.Namespace) -> bool:
    return bool(args.skip_git_repo_check or not is_git_worktree(Path(args.workspace).resolve()))


def execute(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    workspace = Path(args.workspace).resolve()
    Path(args.task_dir).resolve()
    prompt_file = Path(args.prompt_file).resolve()
    output_last_message = Path(args.output_last_message).resolve()
    stdout_log = Path(args.stdout_log).resolve()
    stderr_log = Path(args.stderr_log).resolve()
    status_json = Path(args.status_json).resolve()
    command = build_command(args)
    status = base_status(args, command)

    output_last_message.parent.mkdir(parents=True, exist_ok=True)
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    stderr_log.parent.mkdir(parents=True, exist_ok=True)
    status_json.parent.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        status['started_at'] = utc_now()
        status['finished_at'] = status['started_at']
        status['output_last_message_exists'] = output_last_message.exists()
        write_json(status_json, status)
        print(json.dumps(status, ensure_ascii=True, indent=2))
        return 0, status

    if not workspace.exists():
        status.update({'status': 'spawn_failed', 'error_summary': f'Missing workspace: {workspace}'})
        status['finished_at'] = utc_now()
        write_json(status_json, status)
        print(json.dumps(status, ensure_ascii=True, indent=2))
        return 127, status
    if not prompt_file.exists():
        status.update({'status': 'spawn_failed', 'error_summary': f'Missing prompt file: {prompt_file}'})
        status['finished_at'] = utc_now()
        write_json(status_json, status)
        print(json.dumps(status, ensure_ascii=True, indent=2))
        return 127, status

    env = os.environ.copy()
    if args.codex_home:
        env['CODEX_HOME'] = str(Path(args.codex_home).resolve())
    env['PYTHONIOENCODING'] = 'utf-8'
    env['NO_COLOR'] = '1'
    prompt = prompt_file.read_text(encoding='utf-8', errors='replace')

    started_clock = time.monotonic()
    state: dict[str, Any] = {
        'stdout': [],
        'stderr': [],
        'stdout_bytes': 0,
        'stderr_bytes': 0,
        'last_output_at': started_clock,
    }
    lock = threading.Lock()
    status['started_at'] = utc_now()
    proc = None
    try:
        proc = subprocess.Popen(
            command,
            cwd=workspace,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
        )
        assert proc.stdin is not None
        assert proc.stdout is not None
        assert proc.stderr is not None
        stdout_thread = threading.Thread(
            target=stream_reader, args=(proc.stdout, stdout_log, state, 'stdout', lock), daemon=True
        )
        stderr_thread = threading.Thread(
            target=stream_reader, args=(proc.stderr, stderr_log, state, 'stderr', lock), daemon=True
        )
        stdout_thread.start()
        stderr_thread.start()
        proc.stdin.write(prompt)
        proc.stdin.close()

        status_text = 'running'
        while True:
            returncode = proc.poll()
            now = time.monotonic()
            if returncode is not None:
                status['returncode'] = returncode
                status_text = 'succeeded' if returncode == 0 else 'failed'
                break
            if args.timeout_seconds and now - started_clock > args.timeout_seconds:
                status_text = 'timeout'
                status['returncode'] = 124
                kill_process_tree(proc.pid)
                break
            with lock:
                last_output_at = float(state.get('last_output_at') or started_clock)
            if args.no_output_timeout_seconds and now - last_output_at > args.no_output_timeout_seconds:
                status_text = 'no_output_timeout'
                status['returncode'] = 124
                kill_process_tree(proc.pid)
                break
            time.sleep(0.2)

        if status_text in {'timeout', 'no_output_timeout'}:
            try:
                proc.terminate()
            except OSError:
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError:
                    pass
        stdout_thread.join(timeout=10)
        stderr_thread.join(timeout=10)
        status['status'] = status_text
    except FileNotFoundError as exc:
        status.update({'status': 'spawn_failed', 'returncode': 127, 'error_summary': str(exc)})
    except Exception as exc:
        status.update({'status': 'exception', 'returncode': 1, 'error_summary': f'{type(exc).__name__}: {exc}'})
        if proc and proc.poll() is None:
            kill_process_tree(proc.pid)
    finally:
        status['finished_at'] = utc_now()
        status['duration_seconds'] = round(time.monotonic() - started_clock, 3)
        with lock:
            stdout_text = ''.join(state.get('stdout') or [])
            stderr_text = ''.join(state.get('stderr') or [])
            status['stdout_bytes'] = int(state.get('stdout_bytes') or 0)
            status['stderr_bytes'] = int(state.get('stderr_bytes') or 0)
        status['output_last_message_exists'] = output_last_message.exists()
        if not status.get('error_summary'):
            if status['status'] in {'timeout', 'no_output_timeout'}:
                status['error_summary'] = status['status']
            elif status['status'] == 'failed':
                status['error_summary'] = (stderr_text or stdout_text)[-1000:]
        status['transient_failure_suspected'] = transient_suspected(
            stdout_text, stderr_text, status.get('error_summary', '')
        )
        write_json(status_json, status)
    print(json.dumps(status, ensure_ascii=True, indent=2))
    return int(status.get('returncode') or 0), status


def main() -> int:
    parser = argparse.ArgumentParser(description='Stable adapter for codex exec with Windows-safe logs and status.')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--task-dir', required=True)
    parser.add_argument('--prompt-file', required=True)
    parser.add_argument('--output-last-message', required=True)
    parser.add_argument('--codex-home', default='')
    parser.add_argument(
        '--sandbox', choices=['workspace-write', 'read-only', 'danger-full-access'], default='workspace-write'
    )
    parser.add_argument('--timeout-seconds', type=int, default=1800)
    parser.add_argument('--no-output-timeout-seconds', type=int, default=600)
    parser.add_argument('--stdout-log', required=True)
    parser.add_argument('--stderr-log', required=True)
    parser.add_argument('--status-json', required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--skip-git-repo-check', action='store_true')
    parser.add_argument('--extra-codex-arg', action='append', default=[])
    parser.add_argument('--codex-command', default='', help=argparse.SUPPRESS)
    args = parser.parse_args()
    code, _ = execute(args)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
