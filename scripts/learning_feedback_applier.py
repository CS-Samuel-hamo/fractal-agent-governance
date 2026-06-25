#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cross_project_store import load_store, store_dir
from runtime_common import project_root, write_json

FORBIDDEN_EFFECTS = {'execute_blocked_zone', 'skip_checkpoint', 'auto_push', 'auto_merge', 'read_secret'}
ALLOWED_TARGETS = {'map_task_selector', 'worker_router', 'cockpit', 'session_digest'}


def apply_feedback(project: Path) -> dict[str, Any]:
    insights = load_store(project, 'learning_insights').get('insights') or []
    applied = []
    skipped = []
    for item in insights:
        effect = str(item.get('recommended_effect') or '')
        insight_id = str(item.get('insight_id') or '')
        if effect in FORBIDDEN_EFFECTS:
            skipped.append({'insight_id': insight_id, 'reason': 'unsafe_effect_rejected'})
            continue
        if item.get('type') == 'worker_preference':
            target = 'worker_router'
        elif item.get('type') in {'next_action_boost', 'next_action_warning', 'readiness_template'}:
            target = 'map_task_selector'
        elif item.get('type') == 'failure_warning':
            target = 'session_digest'
        else:
            target = 'cockpit'
        if target not in ALLOWED_TARGETS:
            skipped.append({'insight_id': insight_id, 'reason': 'unsupported_target'})
            continue
        applied.append({'target': target, 'insight_id': insight_id, 'effect': effect, 'safe': True})
    payload = {
        'schema_version': '1.0',
        'generated_by': 'learning_feedback_applier.py',
        'applied': applied,
        'skipped': skipped,
    }
    write_json(store_dir(project) / 'learning_feedback_applied.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Apply advisory learning feedback to ranking and display surfaces.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = apply_feedback(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
