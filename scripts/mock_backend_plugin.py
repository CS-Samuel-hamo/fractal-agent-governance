#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from execution_interface import ExecutionBackend, ExecutionContext, ExecutionResult, ExecutionTask


class MockExecutionBackend(ExecutionBackend):
    name = 'mock'

    def health(self) -> dict[str, object]:
        return {'backend': self.name, 'available': True, 'mode': 'test_double'}

    def execute(self, task: ExecutionTask, context: ExecutionContext) -> ExecutionResult:
        changed: list[str] = []
        mode = str(context.backend_options.get('mode') or task.metadata.get('mock_mode') or 'success')
        if mode == 'failure':
            return ExecutionResult(
                backend=self.name,
                status='failed',
                returncode=1,
                stdout_tail='{"status":"failed","returncode":1}',
                duration_seconds=0.0,
                metadata={'task_id': task.task_id, 'mode': mode},
            )
        if mode == 'timeout':
            return ExecutionResult(
                backend=self.name,
                status='timeout',
                returncode=124,
                stdout_tail='{"status":"timeout","returncode":124}',
                duration_seconds=0.0,
                metadata={'task_id': task.task_id, 'mode': mode},
            )
        if mode == 'no_delivery':
            return ExecutionResult(
                backend=self.name,
                status='succeeded',
                returncode=0,
                stdout_tail='{"status":"succeeded","returncode":0}',
                duration_seconds=0.0,
                metadata={'task_id': task.task_id, 'mode': mode},
            )

        workspace = context.workspace_path
        for rel in task.allowed_files[:1]:
            path = workspace / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = path.read_text(encoding='utf-8', errors='replace') if path.exists() else ''
            path.write_text(existing + '\nMock backend delivered.\n', encoding='utf-8')
            changed.append(rel.replace('\\', '/'))
        return ExecutionResult(
            backend=self.name,
            status='succeeded',
            returncode=0,
            stdout_tail='{"status":"succeeded","returncode":0}',
            duration_seconds=0.0,
            output_diff=changed,
            metadata={'task_id': task.task_id, 'mode': mode},
        )


class DryRunExecutionBackend(ExecutionBackend):
    name = 'dry_run'

    def health(self) -> dict[str, object]:
        return {'backend': self.name, 'available': True, 'mode': 'dry_run'}

    def execute(self, task: ExecutionTask, context: ExecutionContext) -> ExecutionResult:
        return ExecutionResult(
            backend=self.name,
            status='dry_run',
            returncode=0,
            stdout_tail='{"status":"dry_run","returncode":0}',
            duration_seconds=0.0,
            metadata={'task_id': task.task_id, 'objective': task.objective},
        )


def create_backend() -> MockExecutionBackend:
    return MockExecutionBackend()


def create_dry_run_backend() -> DryRunExecutionBackend:
    return DryRunExecutionBackend()
