#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


WORKER_RESULT_SCHEMA_VERSION = '1.0'


@dataclass
class WorkerResult:
    worker_name: str
    worker_type: str
    provider: str
    status: str
    changed_files: list[str] = field(default_factory=list)
    summary: str = ''
    confidence: float = 0.0
    error_type: str = ''
    raw_log_path: str = ''
    safe_for_user_output: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            'schema_version': WORKER_RESULT_SCHEMA_VERSION,
            'worker_name': self.worker_name,
            'worker_type': self.worker_type,
            'provider': self.provider,
            'status': self.status,
            'changed_files': self.changed_files,
            'summary': self.summary,
            'confidence': round(max(0.0, min(1.0, float(self.confidence))), 3),
            'error_type': self.error_type,
            'raw_log_path': self.raw_log_path,
            'safe_for_user_output': bool(self.safe_for_user_output),
        }


class Worker(Protocol):
    name: str
    worker_type: str
    provider: str
    capabilities: list[str]

    def health(self) -> dict[str, Any]:
        ...

    def can_handle(self, task_profile: dict[str, Any]) -> bool:
        ...

    def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        ...


def worker_result(
    *,
    worker_name: str,
    worker_type: str,
    provider: str,
    status: str,
    changed_files: list[str] | None = None,
    summary: str = '',
    confidence: float = 0.0,
    error_type: str = '',
    raw_log_path: str = '',
    safe_for_user_output: bool = True,
) -> dict[str, Any]:
    return WorkerResult(
        worker_name=worker_name,
        worker_type=worker_type,
        provider=provider,
        status=status,
        changed_files=changed_files or [],
        summary=summary,
        confidence=confidence,
        error_type=error_type,
        raw_log_path=raw_log_path,
        safe_for_user_output=safe_for_user_output,
    ).to_dict()
