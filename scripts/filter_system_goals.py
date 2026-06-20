#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from classify_goal_domain import classify_goal  # noqa: E402
from goal_state_manager import load_goal_state, sync_goals  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


def filter_goals(state: dict[str, Any]) -> dict[str, Any]:
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    exclusion_reason: dict[str, str] = {}
    for goal in state.get('goals') or []:
        classified = classify_goal(goal)
        goal_id = str(goal.get('goal_id') or '')
        record = {
            'goal_id': goal_id,
            'goal_type': classified['goal_type'],
            'status': goal.get('status'),
            'priority': goal.get('priority'),
            'resource_usage': goal.get('resource_usage') or [],
        }
        if classified['scheduling_allowed']:
            eligible.append(record)
        else:
            reason = f"excluded_{classified['goal_type']}"
            excluded.append(record)
            exclusion_reason[goal_id] = reason
    return {
        'eligible_goals': eligible,
        'excluded_goals': excluded,
        'exclusion_reason': exclusion_reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Filter non-production goals out of the production scheduler queue.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--json-output', default='')
    parser.add_argument('--no-sync', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    state = load_goal_state(project) if args.no_sync else sync_goals(project)
    result = {
        'schema_version': '1.0',
        'generated_by': 'filter_system_goals.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        **filter_goals(state),
    }
    if args.json_output:
        write_json(Path(args.json_output).resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
