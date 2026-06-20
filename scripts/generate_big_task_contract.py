#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import build_big_task_contract, common_big_task_parser, project_root, write_big_task_contract  # noqa: E402


def main() -> int:
    parser = common_big_task_parser('Generate a 0.5.0 big task contract.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    run_id = args.run_id or 'run-big-task'
    text = args.input_text or ' '.join(args.input).strip()
    if not text:
        print('Missing big task input.', file=sys.stderr)
        return 2
    contract = build_big_task_contract(project, run_id, text, goal_id=args.goal_id)
    paths = write_big_task_contract(project, contract)
    report = {'status': 'ok', 'workspace': str(project), 'contract': contract, 'paths': paths}
    if args.json_output:
        Path(args.json_output).resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if not str(contract.get('readiness_verdict', '')).startswith('BLOCKED') else 10


if __name__ == '__main__':
    raise SystemExit(main())
