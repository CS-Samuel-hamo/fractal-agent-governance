#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json

FAILURE_TYPES = {'none', 'timeout', 'partial', 'no_delivery', 'wrong_output'}


def _leaf_execution_statuses(execution: dict[str, Any]) -> list[str]:
    statuses: list[str] = []
    for leaf in execution.get('leaf_results') or []:
        model = leaf.get('execution_model') if isinstance(leaf.get('execution_model'), dict) else {}
        for value in [
            model.get('execution_status'),
            leaf.get('execution_status'),
            leaf.get('backend_status'),
            leaf.get('delivery_outcome'),
        ]:
            if value:
                statuses.append(str(value).lower())
    return statuses


def classify_failure_mode(
    *,
    execution: dict[str, Any],
    final_result: dict[str, Any],
    stage_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stage_results = stage_results or {}
    statuses = _leaf_execution_statuses(execution)
    outcomes = [str(item.get('delivery_outcome') or '').lower() for item in execution.get('leaf_results') or []]
    verdict = str(final_result.get('final_verdict') or '').upper()

    if any((stage_results.get(stage) or {}).get('returncode') for stage in ['planner', 'executor', 'verifier']):
        return {
            'failure_type': 'wrong_output',
            'reason': 'pipeline_stage_nonzero_returncode',
            'is_backend_failure': False,
            'is_task_failure': True,
        }
    if any(status in {'timeout', 'no_output_timeout'} for status in statuses):
        return {
            'failure_type': 'timeout',
            'reason': 'backend_or_execution_timeout',
            'is_backend_failure': True,
            'is_task_failure': False,
        }
    if any(status == 'partial' for status in statuses) or verdict == 'PARTIAL':
        return {
            'failure_type': 'partial',
            'reason': 'partial_completion_detected',
            'is_backend_failure': False,
            'is_task_failure': True,
        }
    if any(outcome == 'no_delivery' for outcome in outcomes) or verdict == 'NO_DELIVERY':
        return {
            'failure_type': 'no_delivery',
            'reason': 'execution_finished_without_business_delivery',
            'is_backend_failure': False,
            'is_task_failure': True,
        }
    if verdict in {'BLOCKED', 'NEEDS_DELIVERY_VERIFICATION'}:
        return {
            'failure_type': 'wrong_output',
            'reason': 'verifier_did_not_accept_execution_result',
            'is_backend_failure': False,
            'is_task_failure': True,
        }
    return {
        'failure_type': 'none',
        'reason': 'no_failure_detected',
        'is_backend_failure': False,
        'is_task_failure': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify pipeline execution failure mode for internal runtime use.')
    parser.add_argument('--execution-result', required=True)
    parser.add_argument('--final-result', required=True)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    payload = classify_failure_mode(
        execution=load_json(Path(args.execution_result).resolve()),
        final_result=load_json(Path(args.final_result).resolve()),
    )
    if args.output:
        path = Path(args.output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
