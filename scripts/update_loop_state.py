#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import initialize_loop, project_root, utc_now, write_json

BACKEND_FAILURE_OUTCOMES = {'blocked'}


def update_state(
    project: Path,
    *,
    run_id: str,
    goal_id: str,
    route: str,
    delivery_outcome: str,
    failure_type: str = '',
    doc_only: bool = False,
    local_optimization: bool = False,
    phase: str = '',
    decomposition_round: bool = False,
    leaf_redo: bool = False,
    max_iterations: int = 5,
) -> dict[str, Any]:
    state = initialize_loop(project, max_iteration=max_iterations, source='update_loop_state.py')
    state['run_id'] = run_id
    state['goal_id'] = goal_id or state.get('goal_id', '')
    state['last_route'] = route or 'unknown'
    if phase:
        state['phase'] = phase
    state['last_delivery_outcome'] = delivery_outcome
    state['max_iterations'] = int(state.get('max_iterations') or state.get('max_iteration') or max_iterations)
    state['max_iteration'] = state['max_iterations']
    state['iteration'] = int(state.get('iteration') or 0)

    if delivery_outcome == 'no_delivery':
        state['no_delivery_count'] = int(state.get('no_delivery_count') or 0) + 1
    elif delivery_outcome in {'delivered', 'no_op_with_evidence'}:
        state['no_delivery_count'] = 0

    if failure_type and failure_type not in {'no_delivery', 'scope_violation', 'none'}:
        state['backend_failure_count'] = int(state.get('backend_failure_count') or 0) + 1
    elif delivery_outcome in {'delivered', 'no_op_with_evidence'}:
        state['backend_failure_count'] = 0

    if failure_type in {'scope_violation', 'denied_files_touched'} or delivery_outcome == 'unsafe':
        state['scope_violation_count'] = int(state.get('scope_violation_count') or 0) + 1

    if doc_only:
        state['doc_only_count'] = int(state.get('doc_only_count') or 0) + 1
    if local_optimization:
        state['local_optimization_count'] = int(state.get('local_optimization_count') or 0) + 1
    if decomposition_round:
        state['decomposition_rounds'] = int(state.get('decomposition_rounds') or 0) + 1
        state['max_decomposition_rounds'] = int(state.get('max_decomposition_rounds') or 2)
    if leaf_redo:
        state['leaf_redo_count'] = int(state.get('leaf_redo_count') or 0) + 1
        state['max_leaf_redo_count'] = int(state.get('max_leaf_redo_count') or 2)

    state['progress_score'] = 1.0 if delivery_outcome == 'delivered' else float(state.get('progress_score') or 0.0)
    state['last_decision'] = 'continue'
    state['next_action'] = 'continue'
    if delivery_outcome == 'delivered':
        state['status'] = 'converged'
        state['last_decision'] = 'converged'
        state['next_action'] = 'review_diff_before_merge'
    elif int(state.get('no_delivery_count') or 0) >= 2:
        state['status'] = 'stopped'
        state['last_decision'] = 'stop_no_delivery_loop'
        state['next_action'] = 'clarify_task_before_actual_run'
    elif int(state.get('backend_failure_count') or 0) >= 2:
        state['status'] = 'stopped'
        state['last_decision'] = 'dry_run_only_backend_unstable'
        state['next_action'] = 'switch_to_dry_run_or_manual_task_pack'
    elif int(state.get('doc_only_count') or 0) >= 2:
        state['status'] = 'blocked'
        state['last_decision'] = 'implementation_pass_required'
        state['next_action'] = 'schedule_implementation_pass'
    elif int(state.get('local_optimization_count') or 0) >= 2:
        state['status'] = 'converged'
        state['last_decision'] = 'defer_local_optimization'
        state['next_action'] = 'record_follow_up'
    elif int(state.get('decomposition_rounds') or 0) > int(state.get('max_decomposition_rounds') or 2):
        state['status'] = 'diverging'
        state['last_decision'] = 'max_decomposition_rounds_reached'
        state['next_action'] = 'GPT_or_human_decision'
    elif int(state.get('leaf_redo_count') or 0) > int(state.get('max_leaf_redo_count') or 2):
        state['status'] = 'blocked'
        state['last_decision'] = 'max_leaf_redo_count_reached'
        state['next_action'] = 'clarify_leaf_contracts'
    elif int(state.get('iteration') or 0) >= int(state.get('max_iterations') or max_iterations):
        state['status'] = 'diverging'
        state['last_decision'] = 'max_iterations_reached'
        state['next_action'] = 'agent loop explain'
    else:
        state['status'] = state.get('status') if state.get('status') in {'active', 'diverging'} else 'active'

    state['updated_at'] = utc_now()
    write_json(project / '.zoo-agent' / 'loop' / 'loop-state.json', state)
    write_json(project / '.zoo-agent' / 'loop_state.json', state)
    if run_id:
        write_json(project / '.zoo-agent' / 'runs' / run_id / 'loop_state.json', state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description='Update lightweight loop state from route/delivery/backend outcome.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--route', default='unknown')
    parser.add_argument('--delivery-outcome', default='')
    parser.add_argument('--failure-type', default='')
    parser.add_argument('--doc-only', action='store_true')
    parser.add_argument('--local-optimization', action='store_true')
    parser.add_argument(
        '--phase',
        choices=['', 'readiness', 'decomposition', 'leaf_dry_run', 'leaf_actual', 'aggregation', 'integration_check'],
        default='',
    )
    parser.add_argument('--decomposition-round', action='store_true')
    parser.add_argument('--leaf-redo', action='store_true')
    parser.add_argument('--max-iterations', type=int, default=5)
    args = parser.parse_args()
    project = project_root(args.workspace)
    state = update_state(
        project,
        run_id=args.run_id,
        goal_id=args.goal_id,
        route=args.route,
        delivery_outcome=args.delivery_outcome,
        failure_type=args.failure_type,
        doc_only=args.doc_only,
        local_optimization=args.local_optimization,
        phase=args.phase,
        decomposition_round=args.decomposition_round,
        leaf_redo=args.leaf_redo,
        max_iterations=args.max_iterations,
    )
    print(json.dumps({'status': 'ok', 'workspace': str(project), 'loop_state': state}, ensure_ascii=True, indent=2))
    return 0 if state.get('status') not in {'stopped', 'blocked', 'diverging'} else 10


if __name__ == '__main__':
    raise SystemExit(main())
