#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

from execution_interface import ExecutionBackend, ExecutionContext, ExecutionResult, ExecutionTask

ROOT = Path(__file__).resolve().parents[1]


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
    return 'codex'


class CodexExecutionBackend(ExecutionBackend):
    name = 'codex'

    def health(self) -> dict[str, object]:
        codex = resolve_codex_command()
        proc = subprocess.run(
            [codex, '--version'],
            cwd=ROOT,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
        )
        return {
            'backend': self.name,
            'available': proc.returncode == 0,
            'returncode': proc.returncode,
            'version': proc.stdout.strip() or proc.stderr.strip(),
        }

    def execute(self, task: ExecutionTask, context: ExecutionContext) -> ExecutionResult:
        command = [
            sys.executable,
            str(ROOT / 'scripts' / 'run_codex_worker.py'),
            '--workspace',
            str(context.workspace_path),
            '--task-dir',
            str(context.task_dir_path),
            '--sandbox',
            context.sandbox,
            '--timeout-seconds',
            str(context.timeout_seconds),
            '--require-leaf-resolution',
        ]
        codex_home = str(context.backend_options.get('codex_home') or '')
        if codex_home:
            command += ['--codex-home', codex_home]
        if context.dry_run:
            command.append('--dry-run')
        started = time.monotonic()
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
        )
        return ExecutionResult(
            backend=self.name,
            status='completed' if proc.returncode == 0 else 'failed',
            returncode=proc.returncode,
            stdout_tail=proc.stdout[-4000:],
            stderr_tail=proc.stderr[-4000:],
            duration_seconds=round(time.monotonic() - started, 3),
            metadata={'command': [str(item) for item in command], 'task_id': task.task_id},
        )


def create_backend() -> CodexExecutionBackend:
    return CodexExecutionBackend()
