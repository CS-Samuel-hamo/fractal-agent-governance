#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from goal_state_manager import load_goal_state  # noqa: E402
from runtime_common import load_json, project_root, write_json  # noqa: E402


CRITICAL_MARKERS = ('api_contract', 'database', 'schema', 'auth_security')


def goals_by_id(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get('goal_id') or ''): item for item in state.get('goals') or [] if item.get('goal_id')}


def event_allows(state: dict[str, Any], goal_id: str, op: str) -> bool:
    for event in state.get('event_log') or []:
        if event.get('goal_id') == goal_id and event.get('op') == op and event.get('reason'):
            return True
    return False


def check_state(state: dict[str, Any], before: dict[str, Any] | None = None) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    goals = state.get('goals') or []
    ids = [str(item.get('goal_id') or '') for item in goals]
    if len(ids) != len(set(ids)):
        blockers.append('duplicate_goal_id')
    active = [item for item in goals if item.get('status') == 'active']
    if len(active) > 1:
        blockers.append('multiple_active_goals')
    for goal in goals:
        goal_id = str(goal.get('goal_id') or '')
        status = str(goal.get('status') or '')
        if not status:
            blockers.append(f'missing_status:{goal_id}')
        if status == 'active' and goal.get('completed'):
            blockers.append(f'completed_goal_active:{goal_id}')
        resources = ' '.join(str(item).lower() for item in goal.get('resource_usage') or [])
        if status == 'active' and any(marker in resources for marker in CRITICAL_MARKERS):
            warnings.append(f'critical_surface_active:{goal_id}')
    if before:
        before_goals = goals_by_id(before)
        after_goals = goals_by_id(state)
        for goal_id, old in before_goals.items():
            new = after_goals.get(goal_id)
            if not new:
                blockers.append(f'goal_removed:{goal_id}')
                continue
            if old.get('priority') != new.get('priority') and not event_allows(state, goal_id, 'set_priority'):
                blockers.append(f'priority_changed_without_patch:{goal_id}')
            if old.get('status') == 'blocked' and new.get('status') == 'paused' and not event_allows(state, goal_id, 'set_status'):
                blockers.append(f'blocked_to_paused_without_reason:{goal_id}')
            if old.get('status') == 'backlog' and new.get('status') == 'paused' and not event_allows(state, goal_id, 'set_status'):
                blockers.append(f'backlog_to_paused_without_reason:{goal_id}')
            if old.get('resource_usage') != new.get('resource_usage') and not event_allows(state, goal_id, 'set_resource_usage'):
                blockers.append(f'resource_usage_changed_without_patch:{goal_id}')
    return {
        'status': 'pass' if not blockers else 'fail',
        'blockers': blockers,
        'warnings': warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Check multi-goal state invariants.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--before', default='')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    state = load_goal_state(project)
    before = load_json(Path(args.before).resolve()) if args.before else {}
    report = {
        'schema_version': '1.0',
        'generated_by': 'check_goal_state_invariants.py',
        'workspace': str(project),
        **check_state(state, before or None),
    }
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'pass' else 10


if __name__ == '__main__':
    raise SystemExit(main())
