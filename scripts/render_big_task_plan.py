#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import load_big_task_contract, project_root, render_contract_md


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Render a big task plan from the contract.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    project = project_root(args.workspace)
    contract = load_big_task_contract(project, args.run_id)
    if not contract:
        print('Missing big-task-contract.json.', file=sys.stderr)
        return 2
    text = render_contract_md(contract)
    path = project / '.zoo-agent' / 'runs' / args.run_id / 'big-task-plan.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    report = {'status': 'ok', 'plan_path': str(path), 'readiness_verdict': contract.get('readiness_verdict')}
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
