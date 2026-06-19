#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import goal_coverage, load_big_task_contract, load_leaf_contracts, load_leaf_outcomes, project_root  # noqa: E402
from runtime_common import write_json  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Check parent goal coverage by leaf evidence.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = goal_coverage(load_big_task_contract(project, args.run_id), load_leaf_contracts(project, args.run_id), load_leaf_outcomes(project, args.run_id))
    path = project / '.zoo-agent' / 'runs' / args.run_id / 'goal-coverage-matrix.json'
    write_json(path, report)
    print(json.dumps({'status': 'ok', 'path': str(path), 'coverage': report}, ensure_ascii=True, indent=2))
    return 0 if not report.get('missing') else 10


if __name__ == '__main__':
    raise SystemExit(main())
