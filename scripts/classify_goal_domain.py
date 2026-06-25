#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, utc_now, write_json

GOAL_TYPES = {'system_goal', 'runtime_goal', 'production_goal', 'diagnostic_goal'}
SYSTEM_MARKERS = [
    'bootstrap',
    'runtime maintenance',
    'scheduler self-check',
    'loop repair',
    'agent runtime',
    'cli-first ai agent runtime',
    'operate this project through the cli-first',
]
RUNTIME_MARKERS = ['metrics', 'health', 'codex-health', 'backend health', 'runtime-v4']
DIAGNOSTIC_MARKERS = ['diagnostic', 'debug', 'dry-run', 'smoke test', 'controlled test', 'validation test']


def classify_goal(payload: dict[str, Any]) -> dict[str, Any]:
    explicit = str(payload.get('goal_type') or payload.get('domain') or '').strip()
    if explicit in GOAL_TYPES:
        goal_type = explicit
        basis = [f'explicit:{explicit}']
    else:
        text = ' '.join(
            [
                str(payload.get('goal') or ''),
                str(payload.get('root_goal') or ''),
                str(payload.get('source') or ''),
                str(payload.get('generated_by') or ''),
                ' '.join(str(item) for item in payload.get('success_criteria') or []),
            ]
        ).lower()
        basis: list[str] = []
        goal_type = 'production_goal'
        if any(marker in text for marker in SYSTEM_MARKERS):
            goal_type = 'system_goal'
            basis.append('system_marker')
        elif any(marker in text for marker in RUNTIME_MARKERS):
            goal_type = 'runtime_goal'
            basis.append('runtime_marker')
        elif any(marker in text for marker in DIAGNOSTIC_MARKERS):
            goal_type = 'diagnostic_goal'
            basis.append('diagnostic_marker')
        else:
            basis.append('default_production_goal')

    scheduling_allowed = goal_type == 'production_goal'
    actual_execution_allowed = goal_type == 'production_goal'
    if goal_type == 'diagnostic_goal':
        actual_execution_allowed = False
    return {
        'goal_id': str(payload.get('goal_id') or ''),
        'goal_type': goal_type,
        'scheduling_allowed': scheduling_allowed,
        'actual_execution_allowed': actual_execution_allowed,
        'execution_mode': 'dry_run_only'
        if goal_type == 'diagnostic_goal'
        else ('background_only' if goal_type in {'system_goal', 'runtime_goal'} else 'normal'),
        'basis': basis,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify a goal as system/runtime/production/diagnostic.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--goal-file', default='')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    if args.goal_file:
        payload = load_json(Path(args.goal_file).resolve())
    elif args.goal_id:
        payload = load_json(project / '.zoo-agent' / 'goals' / f'{args.goal_id}.json')
    else:
        payload = load_json(project / '.zoo-agent' / 'goal' / 'current-goal.json')
    result = {
        'schema_version': '1.0',
        'generated_by': 'classify_goal_domain.py',
        'generated_at': utc_now(),
        **classify_goal(payload),
    }
    if args.json_output:
        write_json(Path(args.json_output).resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
