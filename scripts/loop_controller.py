#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import advance_loop, initialize_loop, project_root, write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Initialize, advance, or converge the CLI-first loop state.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--task-id', default='')
    parser.add_argument('--max-iteration', type=int, default=10)
    parser.add_argument('--advance', action='store_true')
    parser.add_argument('--converge', action='store_true')
    parser.add_argument('--mark-drift', action='store_true')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()

    project = project_root(args.workspace)
    if args.advance:
        state = advance_loop(project, run_id=args.run_id or 'manual', task_id=args.task_id or 'manual', max_iteration=args.max_iteration)
    else:
        state = initialize_loop(project, max_iteration=args.max_iteration, source='loop_controller.py')

    if args.converge:
        state['status'] = 'converged'
        state['drift_detected'] = False
    if args.mark_drift:
        state['status'] = 'diverging'
        state['drift_detected'] = True
        state['recommended_escalation'] = 'gpt_decision_layer'
    write_json(project / '.zoo-agent' / 'loop_state.json', state)
    if args.run_id:
        write_json(project / '.zoo-agent' / 'runs' / args.run_id / 'loop_state.json', state)

    report = {'status': 'ok', 'workspace': str(project), 'loop_state': state}
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if state.get('status') != 'diverging' else 10


if __name__ == '__main__':
    raise SystemExit(main())
