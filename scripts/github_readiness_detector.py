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


def release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release'


def evidence(source: str, detail: str) -> dict[str, str]:
    return {'source': source, 'detail': detail}


def has_blocked_risk(project_map: dict[str, Any]) -> bool:
    for item in project_map.get('risks') or []:
        if not isinstance(item, dict):
            continue
        text = (
            f'{item.get("description", "")} {" ".join(str(path) for path in item.get("affected_files") or [])}'.lower()
        )
        if str(item.get('severity') or '').lower() == 'high' and any(
            word in text for word in ['secret', 'auth', 'payment', 'deploy', 'database']
        ):
            return True
    return False


def template_coverage(release_templates: dict[str, Any], project_map: dict[str, Any]) -> bool:
    project_type = str(project_map.get('project_type') or '').lower()
    for item in release_templates.get('templates') or []:
        if not isinstance(item, dict):
            continue
        if item.get('project_type') == project_type or item.get('goal') in {
            'github_alpha',
            'cli_tool_release',
            'public_release',
        }:
            return True
    return False


def detect_github_readiness(project: Path) -> dict[str, Any]:
    git_context = load_json(release_dir(project) / 'git_context.json')
    project_map = load_json(project / '.zoo-agent' / 'map' / 'project_map.json')
    release_templates = load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'release_templates.json')
    learning_insights = load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'learning_insights.json')
    session_history = load_json(project / '.zoo-agent' / 'session' / 'session_history.json')
    cockpit_data = load_json(project / '.zoo-agent' / 'cockpit' / 'cockpit_data.json')

    assets = git_context.get('repo_assets') if isinstance(git_context.get('repo_assets'), dict) else {}
    blockers: list[str] = []
    warnings: list[str] = []
    actions: list[str] = []
    ev: list[dict[str, str]] = []

    def require(condition: bool, key: str, action: str, source: str) -> None:
        if condition:
            ev.append(evidence(source, f'{key} present'))
        else:
            blockers.append(key)
            actions.append(action)
            ev.append(evidence(source, f'{key} missing'))

    require(
        bool(git_context.get('is_git_repo')),
        'git repo not detected',
        'Initialize or run this inside a Git repository.',
        'git_context',
    )
    require(
        bool(assets.get('readme')),
        'README missing',
        'Add a clear README before GitHub release.',
        'git_context.repo_assets',
    )
    require(
        bool(assets.get('install') or assets.get('quickstart')),
        'install or quickstart missing',
        'Add install and quickstart instructions.',
        'git_context.repo_assets',
    )
    require(
        bool(assets.get('tests')),
        'tests or test notes missing',
        'Add tests or a documented validation path.',
        'git_context.repo_assets',
    )
    require(
        bool(assets.get('license')),
        'license decision missing',
        'Add a LICENSE or document the license decision.',
        'git_context.repo_assets',
    )
    if not assets.get('changelog'):
        warnings.append('changelog not present yet')
        actions.append('Generate a changelog draft with agent release.')
        ev.append(evidence('git_context.repo_assets', 'changelog missing'))
    if str(git_context.get('working_tree_status') or 'unknown') == 'unknown':
        warnings.append('working tree status unknown')
    elif str(git_context.get('working_tree_status')) == 'dirty':
        warnings.append('working tree has local changes')
        ev.append(evidence('git_context', 'working tree dirty'))
    if not template_coverage(release_templates, project_map):
        warnings.append('release readiness template coverage is limited')
        actions.append('Run agent learning --build to refresh local release templates.')
    if has_blocked_risk(project_map):
        blockers.append('high severity release risk unresolved')
        actions.append('Resolve high severity project risks before release.')
    if cockpit_data:
        ev.append(evidence('cockpit', 'project cockpit available'))
    if session_history:
        ev.append(evidence('session_history', 'session history available'))
    if learning_insights.get('insights'):
        ev.append(evidence('learning_insights', 'local learning insights available'))

    github_ready = bool(git_context.get('is_git_repo') and assets.get('readme'))
    pr_ready = github_ready and 'README missing' not in blockers and 'tests or test notes missing' not in blockers
    release_ready = pr_ready and not blockers and assets.get('license') and bool(assets.get('changelog'))
    payload = {
        'generated_by': 'github_readiness_detector.py',
        'generated_at': utc_now(),
        'github_ready': bool(github_ready),
        'pr_ready': bool(pr_ready),
        'release_ready': bool(release_ready),
        'blockers': blockers,
        'warnings': warnings,
        'recommended_next_actions': list(dict.fromkeys(actions)),
        'evidence': ev,
    }
    write_json(release_dir(project) / 'github_readiness.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate local GitHub readiness.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = detect_github_readiness(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
