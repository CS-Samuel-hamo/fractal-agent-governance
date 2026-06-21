#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, safe_name, utc_now, write_json  # noqa: E402


def release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release'


def classify_pr_type(changed_files: list[str], readiness_goal: str) -> str:
    if readiness_goal in {'github_alpha', 'public_release', 'cli_tool_release'}:
        return 'release'
    if changed_files and all(path.lower().endswith(('.md', '.rst', '.txt')) or path.startswith('docs/') for path in changed_files):
        return 'docs'
    if any(path.startswith('tests/') or 'test_' in path for path in changed_files):
        return 'tests'
    return 'maintenance'


def risk_from_files(files: list[str], readiness: dict[str, Any]) -> str:
    text = ' '.join(files).lower()
    if readiness.get('must_fix'):
        return 'medium'
    if any(word in text for word in ['auth', 'payment', 'deploy', 'database', 'migration', 'secret']):
        return 'high'
    if len(files) > 10:
        return 'medium'
    return 'low'


def build_pr_plan(project: Path) -> dict[str, Any]:
    git_context = load_json(release_dir(project) / 'git_context.json')
    project_map = load_json(project / '.zoo-agent' / 'map' / 'project_map.json')
    session_history = load_json(project / '.zoo-agent' / 'session' / 'session_history.json')
    release_readiness = load_json(release_dir(project) / 'release_readiness.json')
    learning_insights = load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'learning_insights.json')
    changed_files = [str(item).replace('\\', '/') for item in git_context.get('changed_files') or []]
    goal = str(release_readiness.get('goal') or 'github_alpha')
    pr_type = classify_pr_type(changed_files, goal)
    risk = risk_from_files(changed_files, release_readiness)
    project_name = str(project_map.get('project_name') or project.name)
    title = f'Prepare {project_name} for {goal.replace("_", " ")}'
    if pr_type == 'docs':
        title = f'Update documentation for {project_name}'
    evidence = [
        {'source': 'git_context', 'changed_files_count': git_context.get('changed_files_count', 0)},
        {'source': 'release_readiness', 'stage': release_readiness.get('stage', 'unknown')},
        {'source': 'project_map', 'next_actions': len(project_map.get('next_actions') or [])},
        {'source': 'session_history', 'steps': len(session_history.get('history') or session_history.get('steps') or [])},
        {'source': 'learning_insights', 'insights': len(learning_insights.get('insights') or [])},
    ]
    test_plan = ['Not run in this workflow']
    if git_context.get('repo_assets', {}).get('tests'):
        test_plan.append('Run the project test suite before opening a remote PR.')
    payload = {
        'generated_by': 'pr_plan_generator.py',
        'generated_at': utc_now(),
        'pr_title': title,
        'pr_type': pr_type,
        'summary': 'Local PR plan generated from Project Map, Git context, release readiness, and session history.',
        'changed_areas': changed_files,
        'evidence': evidence,
        'review_focus': release_readiness.get('must_fix') or ['Confirm generated PR text matches the actual diff before publishing.'],
        'risk_level': risk,
        'test_plan': test_plan,
        'rollback_plan': ['Use the latest local checkpoint or Git working tree controls before publishing.'],
        'not_included': [
            'No remote PR was created.',
            'No remote branch was created.',
            'No remote write action was executed.',
        ],
        'recommended_branch_name': safe_name(re.sub(r'[^A-Za-z0-9._-]+', '-', title.lower()))[:64],
    }
    write_json(release_dir(project) / 'pr_plan.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a local PR plan.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_pr_plan(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
