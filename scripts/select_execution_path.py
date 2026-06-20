#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from execution_policy import DEFAULT_DENIED_FILES, ExecutionPolicyInput, select_execution_path  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description='Select the cheapest safe AI execution path for a bounded task.')
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--objective', required=True)
    ap.add_argument('--allowed-file', action='append', default=[])
    ap.add_argument('--denied-file', action='append', default=DEFAULT_DENIED_FILES)
    ap.add_argument('--test-command', action='append', default=[])
    ap.add_argument('--changed-file-estimate', type=int, default=0)
    ap.add_argument('--force-path', default='', choices=['', 'optimistic_worker', 'planned_worker', 'fractal_governed', 'human_gate'])
    ap.add_argument('--governance-level', type=int, choices=[0, 1, 2, 3, 4], default=None)
    ap.add_argument('--output', default='')
    args = ap.parse_args()

    if not args.allowed_file:
        print('At least one --allowed-file is required.', file=sys.stderr)
        return 2

    selection = select_execution_path(
        ExecutionPolicyInput(
            run_id=args.run_id,
            task_id=args.task_id,
            objective=args.objective,
            allowed_files=args.allowed_file,
            denied_files=args.denied_file,
            test_commands=args.test_command,
            changed_file_estimate=args.changed_file_estimate,
            force_path=args.force_path,
            governance_level=args.governance_level,
        )
    )
    selection['selected_at'] = datetime.datetime.utcnow().isoformat() + 'Z'

    text = json.dumps(selection, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
