#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

RETRYABLE_STATUSES = {'timeout'}
RETRYABLE_REASONS = {
    'backend_worker_timeout',
    'backend_worker_spawn_or_exception',
    'response_stream_disconnected',
    'no_output_timeout',
}


def retry_decision(model: dict[str, Any], *, attempt: int, max_retries: int = 2) -> dict[str, Any]:
    status = str(model.get('execution_status') or '')
    reason = str(model.get('reason') or model.get('notes') or '')
    retryable = status in RETRYABLE_STATUSES or reason in RETRYABLE_REASONS
    should_retry = retryable and attempt <= max_retries
    return {
        'attempt': attempt,
        'max_retries': max_retries,
        'retryable': retryable,
        'should_retry': should_retry,
        'backoff_seconds': 2 ** max(0, attempt - 1) if should_retry else 0,
        'reason': 'retryable_transient_failure'
        if should_retry
        else ('retry_limit_reached' if retryable else 'not_retryable'),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Decide whether an execution result should be retried.')
    parser.add_argument('--model', required=True)
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--max-retries', type=int, default=2)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    model_path = Path(args.model).resolve()
    model = json.loads(model_path.read_text(encoding='utf-8-sig'))
    payload = retry_decision(model, attempt=args.attempt, max_retries=args.max_retries)
    if args.output:
        path = Path(args.output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
