#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from goal_state_manager import set_goal_status, upsert_goal_record
from runtime_common import project_root, safe_name, set_active_goal


def main() -> int:
    parser = argparse.ArgumentParser(description='Set the active CLI-first runtime goal.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--goal', default='')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--success-criteria', action='append', default=[])
    parser.add_argument('--constraint', action='append', default=[])
    parser.add_argument('--non-goal', action='append', default=[])
    parser.add_argument('--risk-tolerance', choices=['low', 'medium', 'high'], default='low')
    parser.add_argument('--priority', type=int, default=50)
    parser.add_argument('--resource', action='append', default=[])
    parser.add_argument('--depends-on', action='append', default=[])
    parser.add_argument(
        '--scheduler-status', choices=['active', 'paused', 'completed', 'blocked', 'backlog'], default=''
    )
    parser.add_argument('--clear', action='store_true')
    parser.add_argument('--no-activate', action='store_true')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()

    project = project_root(args.workspace)
    if args.clear:
        current = project / '.zoo-agent' / 'goal' / 'current-goal.json'
        if current.exists():
            payload = json.loads(current.read_text(encoding='utf-8-sig'))
            payload['active'] = False
            payload['status'] = 'cleared'
            current.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        current_run = project / '.zoo-agent' / 'current-run.json'
        if current_run.exists():
            payload = json.loads(current_run.read_text(encoding='utf-8-sig'))
            payload.pop('goal_id', None)
            payload.pop('active_goal_id', None)
            current_run.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        state_path = project / '.zoo-agent' / 'goal' / 'goal_state.json'
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding='utf-8-sig'))
            active_goal_id = str(
                (state.get('global_loop_state') or {}).get('active_goal_id') or state.get('active_goal_id') or ''
            )
            if active_goal_id:
                set_goal_status(project, safe_name(active_goal_id), 'paused')
        report = {'status': 'cleared', 'workspace': str(project), 'goal_path': str(current)}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if not args.goal.strip():
        print('Missing --goal.', file=sys.stderr)
        return 2
    goal = set_active_goal(
        project,
        args.goal,
        goal_id=args.goal_id,
        run_id=args.run_id,
        success_criteria=args.success_criteria,
        constraints=args.constraint,
        non_goals=args.non_goal,
        risk_tolerance=args.risk_tolerance,
        activate=not args.no_activate,
        source='set_goal.py',
    )
    scheduler_status = args.scheduler_status or ('active' if not args.no_activate else 'paused')
    upsert_goal_record(
        project,
        goal=goal,
        status=scheduler_status,
        priority=args.priority,
        resources=args.resource,
        depends_on=args.depends_on,
    )
    report = {
        'status': 'ok',
        'workspace': str(project),
        'goal_id': goal.get('goal_id'),
        'goal_path': goal.get('_path', ''),
        'active': not args.no_activate,
        'goal': goal,
    }
    if args.json_output:
        out = Path(args.json_output).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
