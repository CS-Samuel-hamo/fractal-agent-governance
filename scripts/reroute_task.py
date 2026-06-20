#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, safe_name, utc_now, write_json  # noqa: E402


def run_command(command: list[str], cwd: Path, *, timeout: int = 0) -> dict[str, Any]:
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
        )
        return {
            'command': [str(item) for item in command],
            'cwd': str(cwd),
            'returncode': proc.returncode,
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'command': [str(item) for item in command],
            'cwd': str(cwd),
            'returncode': 124,
            'stdout': exc.stdout or '',
            'stderr': exc.stderr or '',
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': True,
        }


def old_report_path(project: Path, run_id: str, task_id: str) -> Path:
    direct = project / '.zoo-agent' / 'runs' / run_id / 'cli-runtime' / f'{safe_name(task_id)}.json'
    if direct.exists():
        return direct
    matches = sorted((project / '.zoo-agent' / 'runs' / run_id / 'cli-runtime').glob('*.json'))
    for path in matches:
        payload = load_json(path)
        if payload.get('task_id') == task_id:
            return path
    return direct


def route_command(project: Path, args, old_report: dict[str, Any], new_run_id: str, new_task_id: str) -> list[str]:
    classification = old_report.get('classification') if isinstance(old_report.get('classification'), dict) else {}
    input_text = args.input_text or str(old_report.get('input') or '')
    if not input_text:
        raise SystemExit('Unable to reroute: old report has no input text; pass --input-text.')
    goal_id = args.goal_id or str(old_report.get('goal_id') or '')
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'route_task.py'),
        '--workspace',
        str(project),
        '--run-id',
        new_run_id,
        '--task-id',
        new_task_id,
        '--input-text',
        input_text,
        f'--{args.path}',
    ]
    if goal_id:
        command.extend(['--goal-id', goal_id])
    for pattern in classification.get('allowed_files') or []:
        command.extend(['--allowed-file', str(pattern)])
    for pattern in classification.get('denied_files') or []:
        command.extend(['--denied-file', str(pattern)])
    if args.dry_run:
        command.append('--dry-run')
    if args.worker_dry_run:
        command.append('--worker-dry-run')
    if args.no_execute_governed_workers:
        command.append('--no-execute-governed-workers')
    if args.discard_failed_worktree:
        command.append('--discard-failed-worktree')
    if args.codex_home:
        command.extend(['--codex-home', args.codex_home])
    if args.profile:
        command.extend(['--profile', args.profile])
    command.extend(['--timeout-seconds', str(args.timeout_seconds)])
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description='Reroute a previously classified task through a chosen runtime path.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--path', required=True, choices=['fast', 'parallel', 'governed'])
    parser.add_argument('--new-run-id', default='')
    parser.add_argument('--new-task-id', default='')
    parser.add_argument('--input-text', default='')
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--codex-home', default='')
    parser.add_argument('--profile', default='')
    parser.add_argument('--timeout-seconds', type=int, default=360)
    parser.add_argument('--worker-dry-run', action='store_true')
    parser.add_argument('--no-execute-governed-workers', action='store_true')
    parser.add_argument('--discard-failed-worktree', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    project = project_root(args.workspace)
    old_path = old_report_path(project, args.run_id, args.task_id)
    old_report = load_json(old_path)
    if not old_report:
        raise SystemExit(f'Missing old CLI runtime report: {old_path}')

    stamp = time.strftime('%Y%m%d%H%M%S', time.gmtime())
    new_run_id = args.new_run_id or f'{args.run_id}-reroute-{stamp}'
    new_task_id = args.new_task_id or f'{args.task_id}-reroute-{args.path}'
    command = route_command(project, args, old_report, new_run_id, new_task_id)
    result = run_command(command, ROOT, timeout=args.timeout_seconds + 120 if args.timeout_seconds > 0 else 0)
    report = {
        'schema_version': '1.0',
        'generated_by': 'reroute_task.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'old_run_id': args.run_id,
        'old_task_id': args.task_id,
        'old_report_path': str(old_path),
        'old_selected_path': old_report.get('selected_path', ''),
        'new_run_id': new_run_id,
        'new_task_id': new_task_id,
        'forced_path': args.path,
        'status': 'rerouted' if result.get('returncode') == 0 else 'reroute_failed',
        'route_command': command,
        'route_result': result,
        'preserves_old_evidence': True,
    }
    write_json(project / '.zoo-agent' / 'runs' / args.run_id / 'route-audit' / f'{safe_name(args.task_id)}.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(result.get('returncode') or 0)


if __name__ == '__main__':
    raise SystemExit(main())
