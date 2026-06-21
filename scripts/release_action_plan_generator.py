#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


BLOCKED_WORDS = {'secret', 'auth', 'payment', 'deploy', 'database', 'migration', '.env'}


def release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release'


def blocked_action(action: str, risk: str, files: list[str]) -> bool:
    text = f"{action} {risk} {' '.join(files)}".lower()
    return risk == 'high' or any(word in text for word in BLOCKED_WORDS)


def build_action_plan(project: Path) -> dict[str, Any]:
    project_map = load_json(project / '.zoo-agent' / 'map' / 'project_map.json')
    github_readiness = load_json(release_dir(project) / 'github_readiness.json')
    release_readiness = load_json(release_dir(project) / 'release_readiness.json')
    learning_insights = load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'learning_insights.json')
    failure_taxonomy = load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'failure_taxonomy.json')
    next_actions = []
    blocked = []
    step = 1

    for item in github_readiness.get('recommended_next_actions') or []:
        title = str(item)
        row = {
            'step': step,
            'action': title,
            'why_now': 'Required by GitHub readiness checks.',
            'source': 'github_readiness',
            'risk_level': 'low',
            'suggested_command': f'agent start "{title}"',
            'autopilot_eligible': True,
        }
        next_actions.append(row)
        step += 1

    for item in release_readiness.get('recommended_sequence') or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get('action_type') or 'release readiness step')
        row = {
            'step': step,
            'action': title,
            'why_now': str(item.get('reason') or 'Recommended by local release template.'),
            'source': 'learning_template',
            'risk_level': 'low',
            'suggested_command': f'agent start "{title}"',
            'autopilot_eligible': True,
        }
        next_actions.append(row)
        step += 1

    for item in project_map.get('next_actions') or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get('title') or 'Project next action')
        risk = str(item.get('risk_level') or 'unknown').lower()
        files = [str(path) for path in item.get('target_files') or []]
        row = {
            'step': step,
            'action': title,
            'why_now': str(item.get('why_now') or 'Project Map next action.'),
            'source': 'project_map',
            'risk_level': risk,
            'suggested_command': f'agent start "{title}"',
            'autopilot_eligible': bool(item.get('autopilot_eligible', True)) and not blocked_action(title, risk, files),
        }
        if blocked_action(title, risk, files):
            blocked.append({**row, 'reason': 'Blocked or high-risk release area requires attention.'})
        else:
            next_actions.append(row)
            step += 1
        if step > 8:
            break

    for item in learning_insights.get('insights') or []:
        if not isinstance(item, dict):
            continue
        if item.get('recommended_effect') in {'boost', 'warn'} and item.get('message'):
            next_actions.append(
                {
                    'step': step,
                    'action': str(item.get('message')),
                    'why_now': 'Advisory signal from local cross-project learning.',
                    'source': 'learning_insight',
                    'risk_level': 'low',
                    'suggested_command': 'agent cockpit',
                    'autopilot_eligible': False,
                }
            )
            step += 1
            break

    if failure_taxonomy.get('failure_patterns'):
        blocked.append(
            {
                'action': 'Review common release blockers',
                'source': 'failure_taxonomy',
                'reason': 'Known failure patterns are advisory and should be checked before public release.',
                'autopilot_eligible': False,
            }
        )

    unique = []
    seen = set()
    for item in next_actions:
        key = str(item.get('action')).lower()
        if key in seen:
            continue
        seen.add(key)
        item['step'] = len(unique) + 1
        unique.append(item)
    payload = {
        'generated_by': 'release_action_plan_generator.py',
        'generated_at': utc_now(),
        'goal': release_readiness.get('goal') or 'github_alpha',
        'next_actions': unique[:10],
        'blocked_actions': blocked,
        'suggested_session_goal': 'prepare this project for public release',
    }
    write_json(release_dir(project) / 'release_action_plan.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a local release action plan.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_action_plan(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
