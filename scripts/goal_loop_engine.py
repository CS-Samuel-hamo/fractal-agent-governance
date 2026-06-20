#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from goal_completion_detector import (  # noqa: E402
    BLOCKED_VERDICT,
    COMPLETED_VERDICT,
    DIVERGING_VERDICT,
    NEEDS_REPLAN_VERDICT,
    PARTIAL_VERDICT,
    detect_and_write_goal_completion,
)
from next_goal_suggester import suggest_and_write  # noqa: E402
from goal_state_manager import update_goal_from_goal_loop  # noqa: E402
from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


def run_dir(project: Path, run_id: str) -> Path:
    return project / '.zoo-agent' / 'runs' / run_id


def loop_status_for(verdict: str, *, iteration: int, max_iterations: int) -> tuple[str, str, bool]:
    if verdict == COMPLETED_VERDICT:
        return 'converged', 'goal_completed_stop_loop', False
    if iteration > max_iterations:
        return 'waiting_human', 'max_iterations_reached_choose_block_or_next_goal', True
    if verdict == DIVERGING_VERDICT:
        return 'diverging', 'stop_automatic_loop_and_explain', True
    if verdict == BLOCKED_VERDICT:
        return 'blocked', 'resolve_blockers_before_more_execution', False
    if verdict == NEEDS_REPLAN_VERDICT:
        return 'active', 'next_decomposition_loop', False
    if verdict == PARTIAL_VERDICT:
        return 'active', 'continue_goal_driven_loop_or_refine_required_leaf', False
    return 'blocked', 'unknown_goal_completion_state', False


def write_goal_loop_metrics(project: Path, report: dict[str, Any]) -> None:
    metrics_path = project / '.zoo-agent' / 'metrics' / 'goal-loop.json'
    previous = load_json(metrics_path)
    counters = previous.get('counters') if isinstance(previous.get('counters'), dict) else {}
    total = int(counters.get('goal_loop_iterations') or 0) + 1
    completed = int(counters.get('goal_completed_count') or 0) + (1 if report.get('goal_completion_verdict') == COMPLETED_VERDICT else 0)
    converged = int(counters.get('loop_converged_count') or 0) + (1 if report.get('loop_status') == 'converged' else 0)
    stuck = int(counters.get('stuck_loop_count') or 0) + (1 if report.get('loop_status') in {'diverging', 'waiting_human'} else 0)
    over = int(counters.get('over_decomposition_count') or 0) + (1 if report.get('over_decomposition_detected') else 0)
    drift = int(counters.get('goal_drift_count') or 0) + (1 if report.get('drift_detected') else 0)
    leaf_total = int(counters.get('leaf_goal_total_count') or 0) + int(report.get('leaf_total_count') or 0)
    leaf_done = int(counters.get('leaf_goal_contribution_count') or 0) + int(report.get('completed_leaf_count') or 0)
    no_delivery_impact = int(counters.get('no_delivery_goal_impact_count') or 0) + int(report.get('no_delivery_goal_impact') or 0)
    codex_exec_success = int(counters.get('codex_execution_success_count') or 0) + int(report.get('codex_execution_success_count') or 0)
    counters.update(
        {
            'goal_loop_iterations': total,
            'goal_completed_count': completed,
            'loop_converged_count': converged,
            'stuck_loop_count': stuck,
            'over_decomposition_count': over,
            'goal_drift_count': drift,
            'leaf_goal_total_count': leaf_total,
            'leaf_goal_contribution_count': leaf_done,
            'no_delivery_goal_impact_count': no_delivery_impact,
            'codex_execution_success_count': codex_exec_success,
        }
    )
    metrics = {
        'goal_completion_rate': round(completed / total, 4),
        'loop_convergence_rate': round(converged / total, 4),
        'leaf_to_goal_contribution_ratio': round(leaf_done / leaf_total, 4) if leaf_total else 0.0,
        'stuck_loop_rate': round(stuck / total, 4),
        'over_decomposition_rate': round(over / total, 4),
        'no_delivery_goal_impact': no_delivery_impact,
        'codex_execution_success_rate': round(codex_exec_success / max(leaf_done, 1), 4) if leaf_done else 0.0,
        'goal_drift_frequency': round(drift / total, 4),
    }
    payload = {
        'schema_version': '1.0',
        'generated_by': 'goal_loop_engine.py',
        'updated_at': utc_now(),
        'metric_keys': list(metrics.keys()),
        'latest_event': report,
        'counters': counters,
        'metrics': metrics,
        'targets': {
            'goal_completion_rate': 'increase',
            'loop_convergence_rate': 'increase',
            'leaf_to_goal_contribution_ratio': 'increase',
            'stuck_loop_rate': 'decrease',
            'over_decomposition_rate': 'decrease',
            'no_delivery_goal_impact': 'decrease',
            'codex_execution_success_rate': 'increase_for_actual_leaf_execution',
            'goal_drift_frequency': 'decrease',
        },
    }
    write_json(metrics_path, payload)


def run_goal_loop(
    project: Path,
    run_id: str,
    *,
    goal_id: str = '',
    max_iterations: int = 10,
    advance: bool = True,
    suggest_next: bool = True,
) -> dict[str, Any]:
    completion = detect_and_write_goal_completion(project, run_id, goal_id, max_iterations=max_iterations)
    matrix = completion['goal_coverage_matrix']
    goal_state = completion['goal_state']
    verdict = str(matrix.get('goal_completion_verdict') or '')
    previous_loop = load_json(run_dir(project, run_id) / 'loop-state.json') or load_json(project / '.zoo-agent' / 'loop' / 'loop-state.json') or {}
    current_iteration = int(previous_loop.get('iteration') or goal_state.get('loop_iteration') or 0)
    iteration = current_iteration + 1 if advance else current_iteration
    max_iterations = int(previous_loop.get('max_iterations') or goal_state.get('max_iterations') or max_iterations)
    loop_status, next_action, drift = loop_status_for(verdict, iteration=iteration, max_iterations=max_iterations)
    if loop_status == 'waiting_human':
        goal_status = 'degraded'
    else:
        goal_status = {
            'converged': 'completed',
            'active': 'active',
            'blocked': 'blocked',
            'diverging': 'degraded',
        }.get(loop_status, goal_state.get('status') or 'active')

    loop_state = {
        **previous_loop,
        'schema_version': '1.0',
        'generated_by': 'goal_loop_engine.py',
        'updated_at': utc_now(),
        'run_id': run_id,
        'goal_id': goal_state.get('goal_id') or goal_id,
        'iteration': iteration,
        'max_iterations': max_iterations,
        'max_iteration': max_iterations,
        'status': loop_status,
        'phase': 'goal_completion',
        'last_route': 'governed',
        'last_delivery_outcome': verdict,
        'progress_score': goal_state.get('progress_score', 0.0),
        'last_decision': next_action,
        'next_action': next_action,
        'drift_detected': drift or bool(matrix.get('stuck_loop_detected')),
    }
    goal_state.update(
        {
            'status': goal_status,
            'loop_iteration': iteration,
            'max_iterations': max_iterations,
            'drift_detected': loop_state['drift_detected'],
            'next_action': next_action,
            'updated_at': utc_now(),
        }
    )
    write_json(run_dir(project, run_id) / 'loop-state.json', loop_state)
    write_json(run_dir(project, run_id) / 'loop_state.json', loop_state)
    write_json(project / '.zoo-agent' / 'loop' / 'loop-state.json', loop_state)
    write_json(project / '.zoo-agent' / 'loop_state.json', loop_state)

    next_goal_report = suggest_and_write(project, run_id, str(goal_state.get('goal_id') or goal_id)) if suggest_next else {}
    if next_goal_report:
        goal_state['next_goal_candidates'] = next_goal_report.get('next_goal_candidates') or []

    report = {
        'schema_version': '1.0',
        'generated_by': 'goal_loop_engine.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'goal_id': goal_state.get('goal_id') or goal_id,
        'goal_completion_verdict': verdict,
        'loop_status': loop_status,
        'goal_status': goal_status,
        'loop_iteration': iteration,
        'max_iterations': max_iterations,
        'progress_score': goal_state.get('progress_score', 0.0),
        'completed_leaf_count': goal_state.get('completed_leaf_count', 0),
        'remaining_leaf_count': goal_state.get('remaining_leaf_count', 0),
        'failed_leaf_count': goal_state.get('failed_leaf_count', 0),
        'leaf_total_count': int(goal_state.get('completed_leaf_count') or 0)
        + int(goal_state.get('remaining_leaf_count') or 0)
        + int(goal_state.get('failed_leaf_count') or 0),
        'no_delivery_goal_impact': len(matrix.get('failed_leaf_ids') or []),
        'codex_execution_success_count': len(matrix.get('codex_execution_success_leaf_ids') or []),
        'over_decomposition_detected': bool(matrix.get('over_decomposition_detected')),
        'drift_detected': loop_state['drift_detected'],
        'next_action': next_action,
        'next_goal_candidates': next_goal_report.get('next_goal_candidates') if next_goal_report else [],
        'paths': {
            **(completion.get('paths') or {}),
            'goal_loop_report': str(run_dir(project, run_id) / 'goal-loop-report.json'),
            'loop_state': str(run_dir(project, run_id) / 'loop-state.json'),
            'next_goal_candidates': str(run_dir(project, run_id) / 'next-goal-candidates.json') if next_goal_report else '',
        },
    }
    patch_paths = update_goal_from_goal_loop(project, report) or {}
    report['paths'].update(patch_paths)
    write_json(run_dir(project, run_id) / 'goal-loop-report.json', report)
    write_goal_loop_metrics(project, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Run one goal-driven execution loop decision after parent aggregation.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--max-iterations', type=int, default=10)
    parser.add_argument('--no-advance', action='store_true')
    parser.add_argument('--no-next-goal-suggestions', action='store_true')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = run_goal_loop(
        project,
        args.run_id,
        goal_id=args.goal_id,
        max_iterations=args.max_iterations,
        advance=not args.no_advance,
        suggest_next=not args.no_next_goal_suggestions,
    )
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report.get('goal_completion_verdict') == COMPLETED_VERDICT else 10


if __name__ == '__main__':
    raise SystemExit(main())
