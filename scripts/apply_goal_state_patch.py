#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from goal_state_manager import apply_goal_state_patch_data
from runtime_common import load_json, project_root, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description='Apply a validated patch to multi-goal state.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--patch', required=True)
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    patch = load_json(Path(args.patch).resolve())
    if not patch:
        raise SystemExit('Missing or invalid patch file.')
    try:
        result = apply_goal_state_patch_data(project, patch)
    except Exception as exc:
        report = {'status': 'rejected', 'reason': str(exc), 'patch': str(Path(args.patch).resolve())}
        if args.json_output:
            write_json(Path(args.json_output).resolve(), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 10
    report = {
        'status': 'applied',
        'workspace': str(project),
        'revision': result['state'].get('revision'),
        'paths': result.get('paths') or {},
        'events': result.get('events') or [],
    }
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
