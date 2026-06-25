#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from goal_completion_detector import detect_and_write_goal_completion
from runtime_common import project_root


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Check parent goal coverage by leaf evidence.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--goal-id', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = detect_and_write_goal_completion(project, args.run_id, args.goal_id)
    matrix = report['goal_coverage_matrix']
    print(
        json.dumps(
            {'status': 'ok', 'paths': report.get('paths') or {}, 'coverage': matrix}, ensure_ascii=True, indent=2
        )
    )
    return 0 if matrix.get('goal_completion_verdict') == 'COMPLETED' else 10


if __name__ == '__main__':
    raise SystemExit(main())
