#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, set_active_goal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Set the active CLI-first runtime goal.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--goal', required=True)
    parser.add_argument('--run-id', default='')
    parser.add_argument('--success-criteria', action='append', default=[])
    parser.add_argument('--constraint', action='append', default=[])
    parser.add_argument('--no-activate', action='store_true')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()

    project = project_root(args.workspace)
    goal = set_active_goal(
        project,
        args.goal,
        goal_id=args.goal_id,
        run_id=args.run_id,
        success_criteria=args.success_criteria,
        constraints=args.constraint,
        activate=not args.no_activate,
        source='set_goal.py',
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
