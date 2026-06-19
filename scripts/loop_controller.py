#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import advance_loop, initialize_loop, project_root, utc_now, write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Initialize, advance, or converge the CLI-first loop state.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--task-id', default='')
    parser.add_argument('--max-iteration', type=int, default=10)
    parser.add_argument('--max-iterations', type=int, default=0)
    parser.add_argument('--advance', action='store_true')
    parser.add_argument('--converge', action='store_true')
    parser.add_argument('--mark-drift', action='store_true')
    parser.add_argument('--reset', action='store_true')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--set-max', action='store_true')
    parser.add_argument('--explain', action='store_true')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()

    project = project_root(args.workspace)
    max_iterations = args.max_iterations or args.max_iteration
    if args.advance:
        state = advance_loop(project, run_id=args.run_id or 'manual', task_id=args.task_id or 'manual', max_iteration=max_iterations)
    else:
        state = initialize_loop(project, max_iteration=max_iterations, source='loop_controller.py')

    if args.reset:
        state.update(
            {
                'run_id': args.run_id,
                'iteration': 0,
                'max_iterations': max_iterations,
                'max_iteration': max_iterations,
                'status': 'active',
                'last_route': 'unknown',
                'last_delivery_outcome': '',
                'progress_score': 0.0,
                'doc_only_count': 0,
                'no_delivery_count': 0,
                'local_optimization_count': 0,
                'backend_failure_count': 0,
                'scope_violation_count': 0,
                'last_decision': 'reset',
                'next_action': 'continue',
                'drift_detected': False,
                'updated_at': utc_now(),
            }
        )
    if args.set_max:
        state['max_iterations'] = max_iterations
        state['max_iteration'] = max_iterations
        state['last_decision'] = 'set_max_iterations'
        state['updated_at'] = utc_now()
    if args.converge:
        state['status'] = 'converged'
        state['drift_detected'] = False
        state['last_decision'] = 'manual_converged'
    if args.stop:
        state['status'] = 'stopped'
        state['last_decision'] = 'manual_stop'
        state['next_action'] = 'wait_for_user'
    if args.mark_drift:
        state['status'] = 'diverging'
        state['drift_detected'] = True
        state['recommended_escalation'] = 'gpt_decision_layer'
    write_json(project / '.zoo-agent' / 'loop' / 'loop-state.json', state)
    write_json(project / '.zoo-agent' / 'loop_state.json', state)
    if args.run_id:
        write_json(project / '.zoo-agent' / 'runs' / args.run_id / 'loop_state.json', state)

    report = {
        'status': 'ok',
        'workspace': str(project),
        'loop_state': state,
        'explanation': {
            'loop_is_loss_controller_not_planner': True,
            'next_action': state.get('next_action', ''),
        } if args.explain else {},
    }
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if state.get('status') != 'diverging' else 10


if __name__ == '__main__':
    raise SystemExit(main())
