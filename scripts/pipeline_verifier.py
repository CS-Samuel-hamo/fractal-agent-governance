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


FORBIDDEN_RESPONSIBILITIES = [
    'planning',
    'goal_selection',
    'scheduling',
    'conflict_detection',
    'backend_execution',
    'worker_spawn',
]


def verdict_from_execution(execution: dict[str, Any]) -> tuple[str, str, bool]:
    leaves = execution.get('leaf_results') or []
    if not leaves:
        return 'BLOCKED', 'no_leaf_results', False
    outcomes = [str(item.get('delivery_outcome') or '') for item in leaves]
    if any(item in {'blocked', 'unsafe'} for item in outcomes):
        return 'BLOCKED', 'one_or_more_leaf_results_blocked_or_unsafe', False
    if all(item in {'delivered', 'no_op_with_evidence'} for item in outcomes):
        return 'COMPLETED', 'all_leaf_results_delivered_or_no_op_with_evidence', True
    if all(item == 'dry_run_only' for item in outcomes):
        return 'DRY_RUN_COMPLETE', 'dry_run_plan_verified_without_actual_execution', False
    if any(item == 'executed_pending_verification' for item in outcomes):
        return 'NEEDS_DELIVERY_VERIFICATION', 'actual_execution_requires_delivery_outcome_check', False
    if any(item == 'no_delivery' for item in outcomes):
        return 'NO_DELIVERY', 'execution_finished_without_business_delivery', False
    return 'PARTIAL', 'mixed_or_unknown_leaf_outcomes', False


def verify_execution(args: argparse.Namespace) -> dict[str, Any]:
    execution_path = Path(args.execution_result).resolve()
    execution = load_json(execution_path)
    if not execution:
        raise SystemExit(f'Missing or invalid execution result: {execution_path}')
    verdict, reason, converged = verdict_from_execution(execution)
    leaf_results = execution.get('leaf_results') or []
    delivery_counts: dict[str, int] = {}
    for item in leaf_results:
        key = str(item.get('delivery_outcome') or 'unknown')
        delivery_counts[key] = delivery_counts.get(key, 0) + 1
    return {
        'schema_version': '1.0',
        'generated_by': 'pipeline_verifier.py',
        'generated_at': utc_now(),
        'stage': 'verifier',
        'run_id': execution.get('run_id', ''),
        'workspace': execution.get('workspace', ''),
        'execution_result_ref': str(execution_path),
        'input_contract': 'execution_result.json',
        'output_contract': 'final_result.json',
        'forbidden_responsibilities': FORBIDDEN_RESPONSIBILITIES,
        'backend_invoked': False,
        'planner_invoked': False,
        'executor_invoked': False,
        'aggregation_role': 'collapsed_into_verifier',
        'loop_role': 'verifier_reports_convergence_only',
        'final_verdict': verdict,
        'goal_converged': converged,
        'reason': reason,
        'delivery_counts': delivery_counts,
        'checks': {
            'execution_result_readable': True,
            'executor_stage_confirmed': execution.get('stage') == 'executor',
            'scheduler_not_used_by_executor': execution.get('scheduler_used') is False,
            'conflict_detector_not_used_by_executor': execution.get('conflict_detector_used') is False,
            'aggregation_not_used_by_executor': execution.get('aggregation_used') is False,
        },
        'next_action': 'stop' if converged or verdict == 'DRY_RUN_COMPLETE' else 'replan_or_clarify',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Verifier stage for the 3-stage Agent Runtime pipeline.')
    parser.add_argument('--execution-result', required=True)
    parser.add_argument('--output', default='')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    result = verify_execution(args)
    output = Path(args.output).resolve() if args.output else Path(args.execution_result).resolve().parent / 'final_result.json'
    write_json(output, result)
    if args.debug:
        payload = {'status': 'ok', 'final_result_json': str(output), 'run_id': result.get('run_id'), 'stage': 'verifier', 'final_verdict': result['final_verdict']}
    else:
        payload = {
            'goal': result.get('run_id') or 'current run',
            'progress': 'complete' if result.get('final_verdict') in {'COMPLETED', 'DRY_RUN_COMPLETE'} else 'in_progress',
            'result': result.get('final_verdict') or 'unknown',
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
