#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import (
    build_big_task_contract,
    classify_readiness,
    common_big_task_parser,
    load_big_task_contract,
    project_root,
    write_big_task_contract,
)


def main() -> int:
    parser = common_big_task_parser('Check the big task readiness gate.')
    parser.add_argument('--contract', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    run_id = args.run_id or 'run-big-task'
    if args.contract:
        contract = json.loads(Path(args.contract).read_text(encoding='utf-8-sig'))
    else:
        contract = load_big_task_contract(project, run_id)
        if not contract:
            text = args.input_text or ' '.join(args.input).strip()
            if not text:
                print('Missing --contract or big task input.', file=sys.stderr)
                return 2
            contract = build_big_task_contract(project, run_id, text, goal_id=args.goal_id)
    verdict, mode, blockers, next_action = classify_readiness(contract)
    contract.update(
        {
            'readiness_verdict': verdict,
            'allowed_execution_mode': mode,
            'blocking_reasons': sorted(set(blockers)),
            'next_action': next_action,
        }
    )
    paths = write_big_task_contract(project, contract)
    report = {
        'status': 'ok',
        'verdict': verdict,
        'allowed_execution_mode': mode,
        'blocking_reasons': sorted(set(blockers)),
        'paths': paths,
        'contract': contract,
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if not verdict.startswith('BLOCKED') else 10


if __name__ == '__main__':
    raise SystemExit(main())
