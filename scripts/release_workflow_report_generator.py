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


READY = 'GITHUB_PR_RELEASE_WORKFLOW_098_READY'
FIX = 'FIX_BEFORE_0981'
NOT_READY = 'NOT_READY'


def release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release'


def exists(project: Path, name: str) -> bool:
    return (release_dir(project) / name).exists()


def final_status(project: Path) -> tuple[str, list[str]]:
    required = [
        'git_context.json',
        'github_readiness.json',
        'release_readiness.json',
        'release_readiness_report.md',
        'pr_plan.json',
        'pr_draft.md',
        'release_notes_draft.md',
        'changelog_draft.md',
        'release_action_plan.json',
        'github_workflow_safety_report.json',
    ]
    missing = [name for name in required if not exists(project, name)]
    safety = load_json(release_dir(project) / 'github_workflow_safety_report.json')
    if safety and not safety.get('safe', False):
        return NOT_READY, ['safety gate failed', *safety.get('failed_checks', [])]
    if missing:
        return FIX, [f'missing {name}' for name in missing]
    return READY, []


def write_report(project: Path) -> dict[str, Any]:
    git_context = load_json(release_dir(project) / 'git_context.json')
    github_ready = load_json(release_dir(project) / 'github_readiness.json')
    readiness = load_json(release_dir(project) / 'release_readiness.json')
    pr_plan = load_json(release_dir(project) / 'pr_plan.json')
    action_plan = load_json(release_dir(project) / 'release_action_plan.json')
    safety = load_json(release_dir(project) / 'github_workflow_safety_report.json')
    status, failures = final_status(project)
    blocker_rows = (
        [f"- {item}" for item in github_ready.get('blockers') or []]
        if github_ready.get('blockers')
        else ['- No hard blocker reported by GitHub readiness.']
    )
    lines = [
        '# Release Workflow Report',
        '',
        '## First impression',
        f'- Final recommendation: {status}',
        '- The workflow generated a local release pack for review and handoff.',
        '',
        '## Git / GitHub context',
        f"- Git repo: {git_context.get('is_git_repo', False)}",
        f"- Branch: {git_context.get('current_branch') or 'unknown'}",
        f"- Working tree: {git_context.get('working_tree_status') or 'unknown'}",
        f"- GitHub remote: {git_context.get('remote', {}).get('provider') == 'github'}",
        '',
        '## Release readiness',
        f"- Stage: {readiness.get('stage') or 'unknown'}",
        f"- Score: {readiness.get('readiness_score')}",
        f"- Blockers: {len(readiness.get('must_fix') or [])}",
        '',
        '## PR plan',
        f"- Draft title: {pr_plan.get('pr_title') or 'not available'}",
        f"- Risk level: {pr_plan.get('risk_level') or 'unknown'}",
        '- PR draft path: .zoo-agent/release/pr_draft.md',
        '',
        '## Release notes status',
        '- Draft path: .zoo-agent/release/release_notes_draft.md',
        '',
        '## Changelog status',
        '- Draft path: .zoo-agent/release/changelog_draft.md',
        '',
        '## Blockers',
        *blocker_rows,
        '',
        '## Suggested next action',
        f"- {action_plan.get('suggested_session_goal') or 'prepare this project for public release'}",
        '- Suggested command: `agent start "prepare this project for public release"`',
        '',
        '## Cockpit integration',
        '- Release / PR artifacts are available for the local Project Cockpit.',
        '',
        '## Safety confirmation',
        f"- Local-only safety gate: {'passed' if safety.get('safe') else 'not passed'}",
        '- No remote publishing action is included in this workflow.',
        '- No token or secret material is required.',
        '',
        '## Should we proceed to 0.98.1 GitHub/PR/Release Dogfood?',
        f'- {status}',
        '',
    ]
    if failures:
        lines.extend(['## Required fixes', *(f'- {item}' for item in failures), ''])
    path = release_dir(project) / 'release_workflow_report.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')
    readiness_payload = {
        'generated_by': 'release_workflow_report_generator.py',
        'generated_at': utc_now(),
        'readiness': status,
        'must_fix_before_0981': failures,
        'recommended_next_steps': ['agent cockpit', 'agent pr', 'agent start "prepare this project for public release"'],
    }
    write_json(release_dir(project) / 'readiness_for_0981.json', readiness_payload)
    return {
        'status': status,
        'report': '.zoo-agent/release/release_workflow_report.md',
        'readiness': readiness_payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate local release workflow report.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = write_report(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('status') != NOT_READY else 1


if __name__ == '__main__':
    raise SystemExit(main())
