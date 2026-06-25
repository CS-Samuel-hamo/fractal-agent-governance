#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class ExecutionTask:
    task_id: str
    objective: str
    allowed_files: list[str] = field(default_factory=list)
    denied_files: list[str] = field(default_factory=list)
    acceptance: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_leaf(cls, leaf: dict[str, Any]) -> ExecutionTask:
        return cls(
            task_id=str(leaf.get('leaf_id') or leaf.get('task_id') or 'leaf'),
            objective=str(leaf.get('objective') or ''),
            allowed_files=[str(item) for item in leaf.get('allowed_files') or []],
            denied_files=[str(item) for item in leaf.get('denied_files') or []],
            acceptance=[str(item) for item in leaf.get('acceptance') or []],
            metadata=dict(leaf),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionContext:
    workspace: str
    task_dir: str
    sandbox: str = 'workspace-write'
    timeout_seconds: int = 360
    dry_run: bool = False
    backend_options: dict[str, Any] = field(default_factory=dict)

    @property
    def workspace_path(self) -> Path:
        return Path(self.workspace).resolve()

    @property
    def task_dir_path(self) -> Path:
        return Path(self.task_dir).resolve()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionResult:
    backend: str
    status: str
    returncode: int | None = None
    stdout_tail: str = ''
    stderr_tail: str = ''
    duration_seconds: float = 0.0
    output_diff: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_worker_result(self) -> dict[str, Any]:
        payload = {
            'backend': self.backend,
            'status': self.status,
            'returncode': self.returncode,
            'stdout_tail': self.stdout_tail,
            'stderr_tail': self.stderr_tail,
            'duration_seconds': self.duration_seconds,
            'output_diff': self.output_diff,
            'metadata': self.metadata,
        }
        if self.status and self.status not in self.stdout_tail:
            payload['stdout_tail'] = (
                '{"status":'
                + repr(self.status).replace("'", '"')
                + ',"returncode":'
                + ('null' if self.returncode is None else str(self.returncode))
                + '}'
            )
        return payload

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionBackend(Protocol):
    name: str

    def health(self) -> dict[str, Any]: ...

    def execute(self, task: ExecutionTask, context: ExecutionContext) -> ExecutionResult: ...
