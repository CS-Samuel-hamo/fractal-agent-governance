#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import (  # noqa: E402
    goal_coverage,
    load_big_task_contract,
    load_leaf_contracts,
    load_leaf_convergence,
    load_leaf_outcomes,
    parent_aggregation,
    project_root,
)
from runtime_common import load_json, resolve_goal, utc_now, write_json  # noqa: E402


COMPLETED_VERDICT = 'COMPLETED'
PARTIAL_VERDICT = 'PARTIAL'
BLOCKED_VERDICT = 'BLOCKED'
DIVERGING_VERDICT = 'DIVERGING'
NEEDS_REPLAN_VERDICT = 'NEEDS_REPLAN'


def run_dir(project: Path, run_id: str) -> Path:
    return project / '.zoo-agent' / 'runs' / run_id


def load_parent_aggregation(project: Path, run_id: str) -> dict[str, Any]:
    path = run_dir(project, run_id) / 'parent-aggregation-report.json'
    report = load_json(path)
    if report:
        report['_path'] = str(path)
        return report
    return parent_aggregation(project, run_id)


def outcome_counts(leaves: list[dict[str, Any]], outcomes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    delivered = []
    failed = []
    no_delivery = []
    blocked = []
    codex_success = []
    for leaf in leaves:
        leaf_id = str(leaf.get('leaf_id') or '')
        payload = outcomes.get(leaf_id) or {}
        outcome = str(payload.get('delivery_outcome') or '')
        worker_status = payload.get('worker_status') if isinstance(payload.get('worker_status'), dict) else {}
        if outcome == 'delivered':
            delivered.append(leaf_id)
            if worker_status.get('status') == 'succeeded' or payload.get('codex_returncode') == 0:
                codex_success.append(leaf_id)
        elif outcome == 'no_delivery':
            no_delivery.append(leaf_id)
            failed.append(leaf_id)
        elif outcome in {'blocked', 'unsafe'}:
            blocked.append(leaf_id)
            failed.append(leaf_id)
    remaining = [
        str(leaf.get('leaf_id') or '')
        for leaf in leaves
        if str(leaf.get('leaf_id') or '') not in set(delivered + failed)
    ]
    return {
        'completed_leaf_ids': delivered,
        'failed_leaf_ids': sorted(set(failed)),
        'codex_execution_success_leaf_ids': codex_success,
        'no_delivery_leaf_ids': no_delivery,
        'blocked_leaf_ids': blocked,
        'remaining_leaf_ids': remaining,
        'completed_leaf_count': len(delivered),
        'failed_leaf_count': len(set(failed)),
        'remaining_leaf_count': len(remaining),
    }


def detect_over_decomposition(loop_state: dict[str, Any], leaf_count: int, coverage_rate: float) -> tuple[bool, list[str]]:
    reasons = []
    decomposition_rounds = int(loop_state.get('decomposition_rounds') or 0)
    max_decomposition_rounds = int(loop_state.get('max_decomposition_rounds') or 2)
    leaf_redo_count = int(loop_state.get('leaf_redo_count') or 0)
    max_leaf_redo_count = int(loop_state.get('max_leaf_redo_count') or 2)
    iteration = int(loop_state.get('iteration') or loop_state.get('loop_iteration') or 0)
    max_iterations = int(loop_state.get('max_iterations') or loop_state.get('max_iteration') or 10)
    if decomposition_rounds > max_decomposition_rounds:
        reasons.append('max_decomposition_rounds_exceeded')
    if leaf_redo_count > max_leaf_redo_count:
        reasons.append('max_leaf_redo_count_exceeded')
    if iteration > max_iterations:
        reasons.append('max_loop_iterations_exceeded')
    if leaf_count > 20 and coverage_rate < 0.5:
        reasons.append('many_leafs_low_goal_coverage')
    return bool(reasons), reasons


def classify_goal_completion(
    *,
    aggregation: dict[str, Any],
    coverage: dict[str, Any],
    convergence: dict[str, Any],
    counts: dict[str, Any],
    loop_state: dict[str, Any],
    over_decomposition: bool,
) -> tuple[str, list[str], str]:
    reasons: list[str] = []
    aggregation_verdict = str(aggregation.get('verdict') or '')
    coverage_rate = float(coverage.get('coverage_rate') or 0.0)
    missing = coverage.get('missing') or []
    unresolved_blockers = aggregation.get('unresolved_blockers') or []
    convergence_failures = int(aggregation.get('convergence_failure_leaf_count') or 0)
    backend_failures = int(aggregation.get('backend_failure_leaf_count') or 0)
    no_delivery_count = int(aggregation.get('no_delivery_leaf_count') or 0)
    if aggregation_verdict == 'READY_FOR_INTEGRATION_WORKTREE' and coverage_rate >= 1.0 and not missing and not unresolved_blockers:
        return COMPLETED_VERDICT, ['all_success_criteria_covered_by_delivered_leaf_evidence'], 'goal_completed'
    if aggregation_verdict in {'BLOCKED', 'HUMAN_DECISION_REQUIRED'} or convergence_failures or backend_failures or unresolved_blockers:
        if aggregation_verdict:
            reasons.append(f'aggregation_verdict:{aggregation_verdict}')
        if convergence_failures:
            reasons.append('leaf_convergence_failure')
        if backend_failures:
            reasons.append('backend_failure_leaf')
        if unresolved_blockers:
            reasons.append('unresolved_leaf_blockers')
        return BLOCKED_VERDICT, reasons, 'human_or_gpt_decision_required'
    if over_decomposition or str(loop_state.get('status') or '') == 'diverging':
        return DIVERGING_VERDICT, ['loop_or_decomposition_not_converging'], 'stop_and_explain_loop'
    if aggregation_verdict == 'NEEDS_REPLANNING' or missing:
        reasons.append('success_criteria_missing_coverage')
        return NEEDS_REPLAN_VERDICT, reasons, 'next_decomposition_loop'
    if aggregation_verdict == 'NEEDS_LEAF_REDO' or no_delivery_count:
        reasons.append('required_leaf_needs_redo_or_no_delivery')
        return PARTIAL_VERDICT, reasons, 'resolve_or_defer_failed_leaf_before_more_execution'
    if counts.get('completed_leaf_count') and coverage_rate < 1.0:
        return PARTIAL_VERDICT, ['leafs_completed_but_goal_not_complete'], 'continue_goal_driven_loop'
    if str(convergence.get('status') or '') == 'resolved':
        return PARTIAL_VERDICT, ['leaf_resolution_complete_but_no_delivery_evidence'], 'leaf_dry_run_or_actual_required'
    return BLOCKED_VERDICT, ['insufficient_goal_completion_evidence'], 'human_or_gpt_decision_required'


def build_goal_completion(project: Path, run_id: str, goal_id: str = '', *, max_iterations: int = 10) -> dict[str, Any]:
    contract = load_big_task_contract(project, run_id)
    goal = resolve_goal(project, goal_id or str(contract.get('goal_id') or ''), run_id)
    leaves = load_leaf_contracts(project, run_id)
    outcomes = load_leaf_outcomes(project, run_id)
    convergence = load_leaf_convergence(project, run_id)
    aggregation = load_parent_aggregation(project, run_id)
    coverage = aggregation.get('root_goal_coverage') or goal_coverage(contract, leaves, outcomes)
    loop_state = load_json(run_dir(project, run_id) / 'loop-state.json') or load_json(run_dir(project, run_id) / 'loop_state.json') or {}
    if max_iterations:
        loop_state.setdefault('max_iterations', max_iterations)
    counts = outcome_counts(leaves, outcomes)
    over_decomposition, over_reasons = detect_over_decomposition(loop_state, len(leaves), float(coverage.get('coverage_rate') or 0.0))
    stuck_leaf_ids = [
        str(item.get('leaf_id'))
        for item in convergence.get('resolutions') or []
        if isinstance(item, dict) and item.get('status') == 'stuck'
    ]
    unreachable_leaf_ids = sorted(set(stuck_leaf_ids + list(counts.get('blocked_leaf_ids') or [])))
    verdict, reasons, next_action = classify_goal_completion(
        aggregation=aggregation,
        coverage=coverage,
        convergence=convergence,
        counts=counts,
        loop_state=loop_state,
        over_decomposition=over_decomposition,
    )
    if over_reasons:
        reasons.extend(over_reasons)
    progress_score = float(coverage.get('coverage_rate') or 0.0)
    goal_state_status = {
        COMPLETED_VERDICT: 'completed',
        PARTIAL_VERDICT: 'active',
        NEEDS_REPLAN_VERDICT: 'active',
        BLOCKED_VERDICT: 'blocked',
        DIVERGING_VERDICT: 'degraded',
    }.get(verdict, 'active')
    matrix = {
        'schema_version': '1.0',
        'generated_by': 'goal_completion_detector.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'goal_id': goal.get('goal_id') or contract.get('goal_id') or goal_id,
        'root_goal': goal.get('root_goal') or contract.get('root_goal') or '',
        'success_criteria': contract.get('success_criteria') or goal.get('success_criteria') or [],
        'satisfied_success_criteria': coverage.get('covered') or [],
        'missing_success_criteria': coverage.get('missing') or [],
        'coverage_rate': progress_score,
        'completed_leaf_ids': counts.get('completed_leaf_ids') or [],
        'remaining_leaf_ids': counts.get('remaining_leaf_ids') or [],
        'failed_leaf_ids': counts.get('failed_leaf_ids') or [],
        'codex_execution_success_leaf_ids': counts.get('codex_execution_success_leaf_ids') or [],
        'unreachable_leaf_ids': unreachable_leaf_ids,
        'stuck_loop_detected': verdict == DIVERGING_VERDICT or bool(stuck_leaf_ids),
        'over_decomposition_detected': over_decomposition,
        'parent_aggregation_verdict': aggregation.get('verdict') or '',
        'goal_completion_verdict': verdict,
        'blocking_reasons': sorted(set(str(item) for item in reasons if item)),
        'next_action': next_action,
    }
    state = {
        'schema_version': '1.0',
        'generated_by': 'goal_completion_detector.py',
        'updated_at': utc_now(),
        'goal_id': matrix['goal_id'],
        'active_goal_id': matrix['goal_id'],
        'status': goal_state_status,
        'progress_score': round(progress_score, 3),
        'completed_leaf_count': int(counts.get('completed_leaf_count') or 0),
        'remaining_leaf_count': int(counts.get('remaining_leaf_count') or 0),
        'failed_leaf_count': int(counts.get('failed_leaf_count') or 0),
        'loop_iteration': int(loop_state.get('iteration') or loop_state.get('loop_iteration') or 0),
        'max_iterations': int(loop_state.get('max_iterations') or loop_state.get('max_iteration') or max_iterations),
        'drift_detected': verdict == DIVERGING_VERDICT or bool(loop_state.get('drift_detected')),
        'next_goal_candidates': [],
        'goal_completion_verdict': verdict,
        'goal_coverage_matrix_ref': str(run_dir(project, run_id) / 'goal-coverage-matrix.json'),
        'parent_aggregation_ref': str(run_dir(project, run_id) / 'parent-aggregation-report.json'),
        'next_action': next_action,
    }
    return {'goal_state': state, 'goal_coverage_matrix': matrix, 'aggregation': aggregation}


def write_goal_completion(project: Path, run_id: str, payload: dict[str, Any]) -> dict[str, str]:
    base = run_dir(project, run_id)
    matrix_path = base / 'goal-coverage-matrix.json'
    completion_path = base / 'goal-completion.json'
    result_path = base / 'goal-loop-result.json'
    write_json(matrix_path, payload['goal_coverage_matrix'])
    completion = {
        'schema_version': '1.0',
        'generated_by': 'goal_completion_detector.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'goal_state_result': payload['goal_state'],
        'goal_coverage_matrix': payload['goal_coverage_matrix'],
    }
    write_json(completion_path, completion)
    write_json(result_path, payload['goal_state'])
    return {
        'goal_coverage_matrix': str(matrix_path),
        'goal_completion': str(completion_path),
        'goal_loop_result': str(result_path),
    }


def detect_and_write_goal_completion(project: Path, run_id: str, goal_id: str = '', *, max_iterations: int = 10) -> dict[str, Any]:
    payload = build_goal_completion(project, run_id, goal_id, max_iterations=max_iterations)
    paths = write_goal_completion(project, run_id, payload)
    payload['paths'] = paths
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Detect whether parent aggregation completes the active goal.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--max-iterations', type=int, default=10)
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    result = detect_and_write_goal_completion(project, args.run_id, args.goal_id, max_iterations=args.max_iterations)
    report = {
        'status': 'ok',
        'workspace': str(project),
        'run_id': args.run_id,
        'goal_completion_verdict': result['goal_coverage_matrix'].get('goal_completion_verdict'),
        'paths': result.get('paths') or {},
    }
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report['goal_completion_verdict'] == COMPLETED_VERDICT else 10


if __name__ == '__main__':
    raise SystemExit(main())
