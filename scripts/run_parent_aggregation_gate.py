#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import parent_aggregation, project_root, write_parent_aggregation
from goal_loop_engine import run_goal_loop


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Run the parent aggregation gate.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--max-iterations', type=int, default=10)
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = parent_aggregation(project, args.run_id)
    paths = write_parent_aggregation(project, args.run_id, report)
    goal_loop = run_goal_loop(project, args.run_id, goal_id=args.goal_id, max_iterations=args.max_iterations)
    print(
        json.dumps(
            {'status': 'ok', 'paths': paths, 'report': report, 'goal_loop': goal_loop}, ensure_ascii=True, indent=2
        )
    )
    return (
        0
        if report.get('verdict') == 'READY_FOR_INTEGRATION_WORKTREE'
        and goal_loop.get('goal_completion_verdict') == 'COMPLETED'
        else 10
    )


if __name__ == '__main__':
    raise SystemExit(main())
