#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def safe_name(value: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in '._-' else '-' for ch in value).strip('-') or 'health'


def run_command(command: list[str], cwd: Path, *, timeout: int = 0, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout or None,
            env=env,
        )
        return {
            'command': [str(item) for item in command],
            'cwd': str(cwd),
            'returncode': proc.returncode,
            'stdout': proc.stdout.strip(),
            'stderr': proc.stderr.strip(),
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'command': [str(item) for item in command],
            'cwd': str(cwd),
            'returncode': 124,
            'stdout': (exc.stdout or '').strip() if isinstance(exc.stdout, str) else '',
            'stderr': (exc.stderr or '').strip() if isinstance(exc.stderr, str) else '',
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': True,
        }
    except Exception as exc:
        return {
            'command': [str(item) for item in command],
            'cwd': str(cwd),
            'returncode': 127,
            'stdout': '',
            'stderr': f'{type(exc).__name__}: {exc}',
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': False,
        }


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def temp_root() -> Path:
    candidate = Path('D:/AI_DEV/temp')
    if candidate.exists():
        return candidate
    return Path(os.environ.get('TEMP') or os.environ.get('TMP') or '.').resolve()


def disk_probe() -> dict[str, Any]:
    target = Path('D:/') if Path('D:/').exists() else temp_root().anchor
    try:
        usage = shutil.disk_usage(str(target))
        return {
            'target': str(target),
            'total_gb': round(usage.total / (1024 ** 3), 3),
            'free_gb': round(usage.free / (1024 ** 3), 3),
            'status': 'pass' if usage.free > 1024 ** 3 else 'warning_low_space',
        }
    except Exception as exc:
        return {'target': str(target), 'status': 'unknown', 'error': f'{type(exc).__name__}: {exc}'}


def resolve_codex_command() -> str:
    for name in ['codex', 'codex.cmd', 'codex.exe', 'codex.bat']:
        found = shutil.which(name)
        if found:
            return found
    return 'codex'


def run_adapter_smoke(args: argparse.Namespace, health_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    timestamp = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    workspace = temp_root() / f'codex-worker-health-{timestamp}'
    workspace.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init'], cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
    task_dir = health_dir / 'adapter-smoke'
    task_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = task_dir / 'prompt.md'
    prompt_file.write_text('Say OK.\n', encoding='utf-8')
    final_message = task_dir / 'codex-final-message.md'
    stdout_log = task_dir / 'codex-stdout.log'
    stderr_log = task_dir / 'codex-stderr.log'
    status_json = task_dir / 'codex-worker-status.json'
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'codex_exec_adapter.py'),
        '--workspace',
        str(workspace),
        '--task-dir',
        str(task_dir),
        '--prompt-file',
        str(prompt_file),
        '--output-last-message',
        str(final_message),
        '--sandbox',
        'read-only',
        '--timeout-seconds',
        str(args.timeout_seconds),
        '--no-output-timeout-seconds',
        str(args.no_output_timeout_seconds),
        '--stdout-log',
        str(stdout_log),
        '--stderr-log',
        str(stderr_log),
        '--status-json',
        str(status_json),
        '--skip-git-repo-check',
    ]
    if args.codex_home:
        command.extend(['--codex-home', args.codex_home])
    result = run_command(command, ROOT, timeout=args.timeout_seconds + 60)
    status = load_json(status_json)
    return result, status


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        '# Codex Worker Health',
        '',
        f"- verdict: {payload['verdict']}",
        f"- generated_at: {payload['generated_at']}",
        f"- codex_home_exists: {payload['codex_home']['exists']}",
        f"- codex_version_returncode: {payload['codex_version'].get('returncode')}",
        f"- adapter_status: {payload['adapter_smoke'].get('status')}",
        f"- output_last_message_exists: {payload['adapter_smoke'].get('output_last_message_exists')}",
        '',
        '## Blockers',
        '',
    ]
    blockers = payload.get('blockers') or []
    lines.extend([f"- {item}" for item in blockers] or ['- none'])
    lines.extend(['', '## Warnings', ''])
    warnings = payload.get('warnings') or []
    lines.extend([f"- {item}" for item in warnings] or ['- none'])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Check local Codex worker execution health without reading auth files.')
    parser.add_argument('--codex-home', default=os.environ.get('CODEX_HOME', ''))
    parser.add_argument('--timeout-seconds', type=int, default=240)
    parser.add_argument('--no-output-timeout-seconds', type=int, default=120)
    parser.add_argument('--skip-real-codex', action='store_true')
    parser.add_argument('--output-dir', default=str(ROOT / '.tmp'))
    args = parser.parse_args()

    out_dir = Path(args.output_dir).resolve()
    timestamp = datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    health_dir = out_dir / f'codex-worker-health-{timestamp}'
    health_dir.mkdir(parents=True, exist_ok=True)
    codex_home = Path(args.codex_home).expanduser().resolve() if args.codex_home else None
    env = os.environ.copy()
    if codex_home:
        env['CODEX_HOME'] = str(codex_home)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['NO_COLOR'] = '1'

    codex_command = resolve_codex_command()
    codex_version = run_command([codex_command, '--version'], ROOT, timeout=60, env=env)
    adapter_result: dict[str, Any] = {'status': 'skipped'}
    adapter_status: dict[str, Any] = {'status': 'skipped'}
    if not args.skip_real_codex:
        adapter_result, adapter_status = run_adapter_smoke(args, health_dir)

    blockers: list[str] = []
    warnings: list[str] = []
    codex_home_exists = bool(codex_home and codex_home.exists())
    if args.codex_home and not codex_home_exists:
        blockers.append('codex_home_unavailable')
    if codex_version.get('returncode') != 0:
        blockers.append('codex_version_failed')
    if not args.skip_real_codex:
        if adapter_status.get('status') != 'succeeded':
            blockers.append('codex_exec_adapter_smoke_failed')
        if not adapter_status.get('output_last_message_exists'):
            blockers.append('codex_output_last_message_missing')
        if adapter_status.get('transient_failure_suspected'):
            warnings.append('transient_codex_failure_suspected')
    disk = disk_probe()
    if disk.get('status') != 'pass':
        warnings.append(str(disk.get('status') or 'disk_probe_warning'))

    verdict = 'HEALTHY'
    if blockers:
        verdict = 'UNHEALTHY'
    elif warnings:
        verdict = 'HEALTHY_WITH_WARNINGS'

    payload = {
        'schema_version': '1.0',
        'generated_by': 'check_codex_worker_health.py',
        'generated_at': utc_now(),
        'verdict': verdict,
        'codex_home': {
            'path': str(codex_home) if codex_home else '',
            'exists': codex_home_exists if codex_home else bool(os.environ.get('CODEX_HOME')),
            'auth_files_read': False,
        },
        'disk': disk,
        'codex_version': codex_version,
        'codex_command': codex_command,
        'adapter_command_result': adapter_result,
        'adapter_smoke': adapter_status,
        'blockers': blockers,
        'warnings': warnings,
        'report_dir': str(health_dir),
    }
    json_path = out_dir / f'codex-worker-health-{timestamp}.json'
    md_path = out_dir / f'codex-worker-health-{timestamp}.md'
    write_json(json_path, payload)
    write_json(out_dir / 'codex-worker-health-latest.json', payload)
    write_markdown(md_path, payload)
    print(json.dumps({'verdict': verdict, 'json': str(json_path), 'markdown': str(md_path), 'blockers': blockers, 'warnings': warnings}, ensure_ascii=True, indent=2))
    return 0 if verdict in {'HEALTHY', 'HEALTHY_WITH_WARNINGS'} else 20


if __name__ == '__main__':
    raise SystemExit(main())
