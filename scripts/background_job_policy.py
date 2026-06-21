#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import project_root, utc_now, write_json


PROJECT_GOAL_TERMS = {
    'project',
    'release',
    'readiness',
    'mvp',
    'roadmap',
    'docs',
    'tests',
    'cockpit',
    'map',
    'prepare',
    'build',
    'improve',
}


def decide_policy(goal: str, *, explicit_preview: bool = False, explicit_apply: bool = False, has_allowed_file: bool = False, existing_job: bool = False) -> dict[str, Any]:
    normalized = goal.lower()
    tokens = {part.strip('.,:;"\'()[]{}') for part in normalized.split()}
    project_like = bool(tokens & PROJECT_GOAL_TERMS) or len(tokens) >= 4
    if explicit_preview or explicit_apply or has_allowed_file:
        mode = 'single_task'
        reason = 'explicit task flag or file scope'
    else:
        mode = 'project_job'
        reason = 'default two-command project job flow'
    hint = ''
    if mode == 'project_job' and not project_like:
        hint = 'This was started as a project job. For one-off edits, use: agent "fix README typo" --apply'
    return {
        'generated_at': utc_now(),
        'goal': goal,
        'mode': mode,
        'project_like': project_like,
        'existing_job': existing_job,
        'reason': reason,
        'hint': hint,
        'true_daemon': False,
        'safe_bounded_progress': True,
    }


def write_policy_report(project: Path, decision: dict[str, Any]) -> dict[str, Any]:
    write_json(project / '.zoo-agent' / 'jobs' / 'background_job_policy.json', decision)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description='Decide product-level background job behavior.')
    parser.add_argument('goal', nargs='*')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--has-allowed-file', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    decision = decide_policy(' '.join(args.goal).strip(), explicit_preview=args.preview, explicit_apply=args.apply, has_allowed_file=args.has_allowed_file)
    write_policy_report(project, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
