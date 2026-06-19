#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, utc_now, write_json  # noqa: E402


BACKEND_TEXT_RULES = [
    ('codex_not_installed', ['not recognized', 'not found', 'no such file', 'cannot find', 'is not installed']),
    ('codex_not_logged_in', ['login', 'not authenticated', 'authentication', 'sign in']),
    ('codex_home_unavailable', ['codex_home', 'home unavailable']),
    ('disk_full', ['disk full', 'no space left']),
    ('trusted_directory_rejected', ['trusted directory', 'untrusted']),
    ('sandbox_spawn_failed', ['sandbox', 'spawn failed']),
    ('windows_sandbox_failed', ['windows sandbox', 'win32', 'job object']),
    ('permission_denied', ['permission denied', 'access is denied']),
    ('config_invalid', ['config', 'toml', 'invalid configuration']),
    ('response_stream_disconnected', ['stream disconnected', 'response stream', 'reconnecting', 'connection reset', 'broken pipe']),
    ('model_capacity', ['capacity', 'overloaded', 'try again later']),
    ('model_error', ['model error', 'internal server error']),
    ('network_unavailable', ['network', 'dns', 'tls', 'connection refused']),
    ('output_last_message_missing', ['output-last-message', 'last message missing']),
]


def text_blob(payload: dict[str, Any], explicit_text: str = '') -> str:
    parts = [explicit_text]
    for key in ['stdout', 'stderr', 'error_summary', 'message', 'reason']:
        value = payload.get(key)
        if isinstance(value, str):
            parts.append(value)
    for nested in ['codex_version', 'adapter_smoke', 'worker_status', 'adapter_command_result']:
        value = payload.get(nested)
        if isinstance(value, dict):
            parts.append(text_blob(value))
    return '\n'.join(parts).lower()


def classify(
    *,
    status_json: Path | None = None,
    text: str = '',
    returncode: int | None = None,
    worker_status: str = '',
    delivery_outcome: str = '',
    scope_guard_status: str = '',
) -> dict[str, Any]:
    payload = load_json(status_json) if status_json else {}
    blob = text_blob(payload, text)
    status = worker_status or str(payload.get('status') or payload.get('worker_execution_status') or '')
    rc = returncode
    if rc is None and payload.get('returncode') is not None:
        try:
            rc = int(payload.get('returncode'))
        except Exception:
            rc = None

    failure_type = ''
    is_backend = False
    is_task = False
    retry = False
    fallback = ''
    user_action = ''

    if delivery_outcome == 'no_delivery':
        failure_type = 'no_delivery'
        is_task = True
        fallback = 'clarify_task_or_manual_task_pack'
        user_action = 'Clarify the requested file/change or inspect codex-final-message.'
    elif scope_guard_status == 'fail' or delivery_outcome in {'unsafe', 'unsafe_delivery'}:
        failure_type = 'scope_violation'
        is_task = True
        fallback = 'human_intervention'
        user_action = 'Review denied files and scope guard output.'
    elif status in {'timeout', 'no_output_timeout'}:
        failure_type = status
        is_backend = True
        retry = True
        fallback = 'dry_run_only'
        user_action = 'Retry later or run dry-run/manual task pack; do not mark task delivered.'
    elif status in {'spawn_failed', 'exception'}:
        failure_type = 'subprocess_spawn_failed' if status == 'spawn_failed' else 'command_failed'
        is_backend = True
        fallback = 'manual_codex_task_pack'
        user_action = 'Inspect worker status and local Codex installation.'
    elif status == 'failed' or (rc is not None and rc != 0):
        failure_type = 'command_failed'
        is_backend = True
        retry = True
        fallback = 'dry_run_only'
        user_action = 'Inspect stdout/stderr and retry only if transient.'

    if not failure_type:
        for candidate, markers in BACKEND_TEXT_RULES:
            if any(marker in blob for marker in markers):
                failure_type = candidate
                is_backend = True
                retry = candidate in {
                    'response_stream_disconnected',
                    'model_capacity',
                    'model_error',
                    'network_unavailable',
                    'timeout',
                }
                fallback = 'dry_run_only' if retry else 'human_intervention'
                user_action = 'Apply configuration remediation or retry only if transient.'
                break

    if not failure_type:
        failure_type = 'none'
        fallback = ''
        user_action = ''

    severity = 'info'
    if failure_type != 'none':
        severity = 'blocking' if failure_type in {
            'codex_not_installed',
            'codex_not_logged_in',
            'codex_home_unavailable',
            'disk_full',
            'trusted_directory_rejected',
            'sandbox_spawn_failed',
            'windows_sandbox_failed',
            'permission_denied',
            'config_invalid',
            'scope_violation',
            'denied_files_touched',
            'unsafe_delivery',
        } else 'warning'

    return {
        'schema_version': '1.0',
        'generated_by': 'classify_codex_failure.py',
        'generated_at': utc_now(),
        'failure_type': failure_type,
        'severity': severity,
        'is_backend_failure': is_backend,
        'is_task_failure': is_task,
        'retry_recommended': retry,
        'fallback_recommended': fallback,
        'user_action': user_action,
        'basis': {
            'status_json': str(status_json) if status_json else '',
            'worker_status': status,
            'returncode': rc,
            'delivery_outcome': delivery_outcome,
            'scope_guard_status': scope_guard_status,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify Codex backend, task, governance, and context failures.')
    parser.add_argument('--status-json', default='')
    parser.add_argument('--text', default='')
    parser.add_argument('--returncode', type=int, default=None)
    parser.add_argument('--worker-status', default='')
    parser.add_argument('--delivery-outcome', default='')
    parser.add_argument('--scope-guard-status', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()

    report = classify(
        status_json=Path(args.status_json).resolve() if args.status_json else None,
        text=args.text,
        returncode=args.returncode,
        worker_status=args.worker_status,
        delivery_outcome=args.delivery_outcome,
        scope_guard_status=args.scope_guard_status,
    )
    if args.output:
        write_json(Path(args.output).resolve(), report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report['failure_type'] == 'none' else (20 if report['severity'] == 'blocking' else 10)


if __name__ == '__main__':
    raise SystemExit(main())
