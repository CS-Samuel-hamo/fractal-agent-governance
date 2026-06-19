#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, resolve_goal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Get the active CLI-first runtime goal.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--require', action='store_true')
    args = parser.parse_args()

    project = project_root(args.workspace)
    goal = resolve_goal(project, args.goal_id, args.run_id)
    report = {
        'status': 'ok' if goal else 'missing',
        'workspace': str(project),
        'goal_id': goal.get('goal_id', args.goal_id) if goal else args.goal_id,
        'goal': goal,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require and not goal:
        return 20
    return 0 if goal or not args.require else 20


if __name__ == '__main__':
    raise SystemExit(main())
