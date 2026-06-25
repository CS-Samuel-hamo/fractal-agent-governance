#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import alignment_report, project_root, safe_name, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description='Check whether a task or review is aligned to the active goal.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--objective', default='')
    parser.add_argument('--review-file', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()

    project = project_root(args.workspace)
    objective = args.objective
    if args.review_file and not objective:
        objective = Path(args.review_file).read_text(encoding='utf-8', errors='replace')[:12000]
    if not objective:
        print('Missing --objective or --review-file.', file=sys.stderr)
        return 2

    report = alignment_report(
        project,
        objective=objective,
        task_id=args.task_id,
        run_id=args.run_id,
        goal_id=args.goal_id,
        source='check_goal_alignment.py',
    )
    output = (
        Path(args.output).resolve()
        if args.output
        else project / '.zoo-agent' / 'runs' / args.run_id / 'goal-alignment' / f'{safe_name(args.task_id)}.json'
    )
    write_json(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report['status'] == 'blocked':
        return 20
    if report['status'] == 'needs_review':
        return 10
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
