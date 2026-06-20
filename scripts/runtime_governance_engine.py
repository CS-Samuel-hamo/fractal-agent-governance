#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, utc_now, write_json


def decide_internal_action(eval_payload: dict[str, Any]) -> dict[str, Any]:
    failure_type = str(eval_payload.get('failure_type') or 'none')
    false_success = bool(eval_payload.get('false_success_detected'))
    quality = float(eval_payload.get('execution_quality_score') or 0.0)
    backend_score = float(eval_payload.get('backend_behavior_score') or 0.0)

    if false_success:
        action = 'escalate'
        reason = 'false_success_detected'
    elif failure_type == 'timeout':
        action = 'fallback' if backend_score < 0.5 else 'retry'
        reason = 'timeout_requires_recovery'
    elif failure_type == 'partial':
        action = 'split'
        reason = 'partial_completion_requires_smaller_execution'
    elif failure_type == 'no_delivery':
        action = 'fallback'
        reason = 'no_delivery_requires_safe_fallback'
    elif failure_type == 'wrong_output':
        action = 'escalate'
        reason = 'verifier_rejected_output'
    elif quality < 0.4:
        action = 'fallback'
        reason = 'low_execution_quality_score'
    else:
        action = 'none'
        reason = 'no_internal_action_required'

    return {
        'schema_version': '1.0',
        'generated_by': 'runtime_governance_engine.py',
        'generated_at': utc_now(),
        'run_id': eval_payload.get('run_id', ''),
        'recommended_internal_action': action,
        'reason': reason,
        'basis': {
            'failure_type': failure_type,
            'false_success_detected': false_success,
            'execution_quality_score': quality,
            'backend_behavior_score': backend_score,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Choose internal recovery action from invisible eval evidence.')
    parser.add_argument('--eval', required=True)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    payload = decide_internal_action(load_json(Path(args.eval).resolve()))
    if args.output:
        write_json(Path(args.output).resolve(), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
