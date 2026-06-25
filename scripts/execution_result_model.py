#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

TRANSIENT_STATUSES = {'timeout', 'no_output_timeout', 'spawn_failed', 'exception'}


def execution_status_from_inputs(
    *,
    backend_returncode: int | None,
    worker_status: str = '',
    business_changed_files: list[str] | None = None,
    expected_files: list[str] | None = None,
    denied_files_touched: list[str] | None = None,
    out_of_scope_files: list[str] | None = None,
) -> tuple[str, str, float]:
    changed = business_changed_files or []
    expected = expected_files or []
    denied = denied_files_touched or []
    out_of_scope = out_of_scope_files or []
    status = (worker_status or '').lower()

    if denied or out_of_scope:
        return 'failed', 'scope_guard_failed', 0.0
    if status in {'timeout', 'no_output_timeout'} or backend_returncode == 124:
        return 'timeout', 'backend_worker_timeout', 0.1
    if status in {'spawn_failed', 'exception'}:
        return 'failed', 'backend_worker_spawn_or_exception', 0.1
    if backend_returncode not in {0, None}:
        return 'failed', 'backend_worker_nonzero_returncode', 0.2
    if changed and expected:
        missing = [item for item in expected if item and item not in changed]
        if missing and len(missing) < len(expected):
            return 'partial', 'some_expected_files_missing', 0.55
        if missing:
            return 'partial', 'expected_files_not_changed', 0.45
    if changed:
        return 'success', 'business_diff_matches_execution', 0.9
    if backend_returncode == 0:
        return 'failed', 'returncode_zero_without_business_diff', 0.25
    return 'unknown', 'insufficient_execution_evidence', 0.0


def delivery_outcome_from_execution_status(status: str) -> str:
    if status == 'success':
        return 'delivered'
    if status == 'partial':
        return 'no_delivery'
    if status == 'timeout':
        return 'blocked'
    if status == 'failed':
        return 'blocked'
    return 'blocked'


def build_execution_result_model(
    *,
    task_id: str,
    backend_returncode: int | None,
    worker_status: str = '',
    business_changed_files: list[str] | None = None,
    expected_files: list[str] | None = None,
    denied_files_touched: list[str] | None = None,
    out_of_scope_files: list[str] | None = None,
    execution_time: float | int | str = '',
    retry_count: int = 0,
    fallback_used: str = '',
    notes: str = '',
) -> dict[str, Any]:
    status, reason, confidence = execution_status_from_inputs(
        backend_returncode=backend_returncode,
        worker_status=worker_status,
        business_changed_files=business_changed_files,
        expected_files=expected_files,
        denied_files_touched=denied_files_touched,
        out_of_scope_files=out_of_scope_files,
    )
    return {
        'task_id': task_id,
        'execution_status': status,
        'confidence': confidence,
        'backend_returncode': '' if backend_returncode is None else backend_returncode,
        'output_diff': business_changed_files or [],
        'expected_files': expected_files or [],
        'execution_time': execution_time,
        'retry_count': retry_count,
        'fallback_used': fallback_used,
        'notes': notes or reason,
        'reason': reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Classify backend execution evidence into a stable execution result model.'
    )
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--backend-returncode', type=int, default=None)
    parser.add_argument('--worker-status', default='')
    parser.add_argument('--business-file', action='append', default=[])
    parser.add_argument('--expected-file', action='append', default=[])
    parser.add_argument('--denied-file-touched', action='append', default=[])
    parser.add_argument('--out-of-scope-file', action='append', default=[])
    parser.add_argument('--execution-time', default='')
    parser.add_argument('--retry-count', type=int, default=0)
    parser.add_argument('--fallback-used', default='')
    parser.add_argument('--notes', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    payload = build_execution_result_model(
        task_id=args.task_id,
        backend_returncode=args.backend_returncode,
        worker_status=args.worker_status,
        business_changed_files=args.business_file,
        expected_files=args.expected_file,
        denied_files_touched=args.denied_file_touched,
        out_of_scope_files=args.out_of_scope_file,
        execution_time=args.execution_time,
        retry_count=args.retry_count,
        fallback_used=args.fallback_used,
        notes=args.notes,
    )
    if args.output:
        path = Path(args.output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
