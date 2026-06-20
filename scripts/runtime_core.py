#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from backend_registry import read_backend_selection, write_backend_selection  # noqa: E402
from runtime_common import load_json, project_root, utc_now  # noqa: E402


class RuntimeCore:
    def __init__(self, workspace: str | Path = '.', backend: str = '') -> None:
        self.workspace = project_root(workspace)
        self.backend = backend or read_backend_selection(self.workspace)

    def _run(self, command: list[str]) -> dict[str, Any]:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return {
            'command': [str(item) for item in command],
            'returncode': proc.returncode,
            'stdout': proc.stdout,
            'stdout_tail': proc.stdout[-4000:],
            'stderr_tail': proc.stderr[-4000:],
        }

    def run_pipeline(
        self,
        input_text: str,
        *,
        run_id: str = '',
        dry_run: bool = True,
        allow_actual: bool = False,
        allowed_files: list[str] | None = None,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        command = [
            sys.executable,
            str(ROOT / 'scripts' / 'pipeline_loop.py'),
            input_text,
            '--workspace',
            str(self.workspace),
            '--backend',
            self.backend,
            '--max-retries',
            str(max_retries),
        ]
        if run_id:
            command += ['--run-id', run_id]
        for item in allowed_files or []:
            command += ['--allowed-file', item]
        if dry_run:
            command.append('--dry-run')
        if allow_actual:
            command.append('--allow-actual')
        result = self._run(command)
        stdout = str(result.get('stdout') or '')
        payload = json.loads(stdout) if result['returncode'] == 0 and stdout.strip().startswith('{') else {}
        result.pop('stdout', None)
        return {
            'status': 'ok' if result['returncode'] == 0 else 'failed',
            'backend': self.backend,
            'runtime_api': 'run_pipeline',
            'result': payload,
            'process': result,
        }

    def run_task(self, task: str, **kwargs: Any) -> dict[str, Any]:
        return self.run_pipeline(task, **kwargs)

    def run_goal(self, goal: str, **kwargs: Any) -> dict[str, Any]:
        goal_id = str(kwargs.pop('goal_id', '') or f'goal-{utc_now().replace(":", "").replace("-", "")}')
        set_goal_cmd = [
            sys.executable,
            str(ROOT / 'scripts' / 'set_goal.py'),
            goal,
            '--workspace',
            str(self.workspace),
            '--goal-id',
            goal_id,
        ]
        goal_result = self._run(set_goal_cmd)
        pipeline = self.run_pipeline(goal, run_id=str(kwargs.pop('run_id', '') or f'run-{goal_id}'), **kwargs)
        return {'status': pipeline['status'], 'goal_result': goal_result, 'pipeline': pipeline}

    def get_status(self) -> dict[str, Any]:
        return {
            'workspace': str(self.workspace),
            'backend': self.backend,
            'backend_selection': read_backend_selection(self.workspace),
            'goal': load_json(self.workspace / '.zoo-agent' / 'goal' / 'current-goal.json'),
            'runtime_api': ['run_goal', 'run_task', 'run_pipeline', 'get_status', 'switch_backend', 'pause', 'resume'],
        }

    def switch_backend(self, backend: str) -> dict[str, Any]:
        path = write_backend_selection(self.workspace, backend)
        self.backend = backend
        return {'status': 'ok', 'backend': backend, 'path': str(path)}

    def pause(self) -> dict[str, Any]:
        path = self.workspace / '.zoo-agent' / 'runtime' / 'runtime-state.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'status': 'paused', 'updated_at': utc_now()}, indent=2), encoding='utf-8')
        return {'status': 'paused', 'path': str(path)}

    def resume(self) -> dict[str, Any]:
        path = self.workspace / '.zoo-agent' / 'runtime' / 'runtime-state.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'status': 'active', 'updated_at': utc_now()}, indent=2), encoding='utf-8')
        return {'status': 'active', 'path': str(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description='Product-grade runtime core facade.')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['run-task', 'run-pipeline', 'run-goal']:
        p = sub.add_parser(name)
        p.add_argument('input')
        p.add_argument('--workspace', default='.')
        p.add_argument('--backend', default='')
        p.add_argument('--run-id', default='')
        p.add_argument('--allowed-file', action='append', default=[])
        p.add_argument('--dry-run', action='store_true')
        p.add_argument('--allow-actual', action='store_true')
    p = sub.add_parser('status')
    p.add_argument('--workspace', default='.')
    p.add_argument('--backend', default='')
    p = sub.add_parser('switch-backend')
    p.add_argument('backend')
    p.add_argument('--workspace', default='.')
    for name in ['pause', 'resume']:
        p = sub.add_parser(name)
        p.add_argument('--workspace', default='.')
        p.add_argument('--backend', default='')
    args = parser.parse_args()
    core = RuntimeCore(getattr(args, 'workspace', '.'), getattr(args, 'backend', ''))
    if args.command == 'run-goal':
        payload = core.run_goal(args.input, run_id=args.run_id, dry_run=args.dry_run, allow_actual=args.allow_actual, allowed_files=args.allowed_file)
    elif args.command == 'run-task':
        payload = core.run_task(args.input, run_id=args.run_id, dry_run=args.dry_run, allow_actual=args.allow_actual, allowed_files=args.allowed_file)
    elif args.command == 'run-pipeline':
        payload = core.run_pipeline(args.input, run_id=args.run_id, dry_run=args.dry_run, allow_actual=args.allow_actual, allowed_files=args.allowed_file)
    elif args.command == 'switch-backend':
        payload = core.switch_backend(args.backend)
    elif args.command == 'pause':
        payload = core.pause()
    elif args.command == 'resume':
        payload = core.resume()
    else:
        payload = core.get_status()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
