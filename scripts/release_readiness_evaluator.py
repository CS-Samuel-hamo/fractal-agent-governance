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


def release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release'


def choose_goal(project_map: dict[str, Any], templates: dict[str, Any]) -> str:
    text = f"{project_map.get('main_goal', '')} {project_map.get('project_type', '')}".lower()
    if 'cli' in text or 'agent' in text:
        return 'cli_tool_release'
    for item in templates.get('templates') or []:
        if isinstance(item, dict) and item.get('goal'):
            return str(item.get('goal'))
    return 'github_alpha'


def matching_template(goal: str, templates: dict[str, Any]) -> dict[str, Any]:
    rows = [item for item in templates.get('templates') or [] if isinstance(item, dict)]
    for item in rows:
        if item.get('goal') == goal or item.get('template_id') == goal:
            return item
    return rows[0] if rows else {}


def build_release_readiness(project: Path) -> dict[str, Any]:
    project_map = load_json(project / '.zoo-agent' / 'map' / 'project_map.json')
    project_state = load_json(project / '.zoo-agent' / 'map' / 'project_state.json')
    templates = load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'release_templates.json')
    pattern_library = load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'pattern_library.json')
    failure_taxonomy = load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'failure_taxonomy.json')
    github_readiness = load_json(release_dir(project) / 'github_readiness.json')

    goal = choose_goal(project_map or project_state, templates)
    template = matching_template(goal, templates)
    blockers = list(github_readiness.get('blockers') or [])
    warnings = list(github_readiness.get('warnings') or [])
    high_risks = [
        item for item in project_map.get('risks') or []
        if isinstance(item, dict) and str(item.get('severity') or '').lower() == 'high'
    ]
    for item in high_risks:
        label = str(item.get('description') or item.get('risk_id') or 'high risk')
        if label not in blockers:
            blockers.append(label)

    score = 1.0
    score -= min(0.7, 0.15 * len(blockers))
    score -= min(0.25, 0.05 * len(warnings))
    if not template:
        score -= 0.1
    score = round(max(0.0, min(1.0, score)), 2)
    if score >= 0.86 and not blockers:
        stage = 'ready'
    elif score >= 0.68:
        stage = 'release_candidate'
    elif score >= 0.42:
        stage = 'getting_ready'
    else:
        stage = 'not_ready'

    recommended = template.get('recommended_sequence') if isinstance(template.get('recommended_sequence'), list) else []
    pattern_evidence = [
        str(item.get('pattern_id')) for item in pattern_library.get('patterns') or []
        if isinstance(item, dict) and item.get('pattern_id')
    ][:8]
    failure_evidence = [
        str(item.get('failure_type')) for item in failure_taxonomy.get('failure_patterns') or []
        if isinstance(item, dict) and item.get('failure_type')
    ][:8]
    payload = {
        'generated_by': 'release_readiness_evaluator.py',
        'generated_at': utc_now(),
        'goal': goal,
        'readiness_score': score,
        'stage': stage,
        'must_fix': blockers,
        'should_fix': warnings,
        'nice_to_have': template.get('nice_to_have') if isinstance(template.get('nice_to_have'), list) else [],
        'evidence': [
            {'source': 'github_readiness', 'items': github_readiness.get('evidence') or []},
            {'source': 'release_template', 'template_id': template.get('template_id', '')},
            {'source': 'learning_patterns', 'patterns': pattern_evidence},
            {'source': 'failure_taxonomy', 'patterns': failure_evidence},
        ],
        'recommended_sequence': recommended,
    }
    write_json(release_dir(project) / 'release_readiness.json', payload)
    write_report(project, payload)
    return payload


def write_report(project: Path, payload: dict[str, Any]) -> None:
    blockers = payload.get('must_fix') or []
    warnings = payload.get('should_fix') or []
    sequence = payload.get('recommended_sequence') or []
    blocker_rows = [f'- {item}' for item in blockers] if blockers else ['- No hard blocker detected.']
    warning_rows = [f'- {item}' for item in warnings] if warnings else ['- No major warning detected.']
    sequence_rows = (
        [f"- Step {item.get('step')}: {item.get('action_type')} - {item.get('reason')}" for item in sequence[:8]]
        if sequence
        else ['- Generate or refresh local release templates, then run agent release again.']
    )
    lines = [
        '# Release Readiness Report',
        '',
        '## Summary',
        f"- Goal: {payload.get('goal')}",
        f"- Stage: {payload.get('stage')}",
        f"- Readiness score: {payload.get('readiness_score')}",
        '',
        '## Current release fit',
        '- This report is local-only and PR-ready oriented; it does not create a remote PR or release.',
        '- Release readiness is based on Git context, Project Map evidence, local session artifacts, and local learning templates.',
        '',
        '## Biggest blockers',
        *blocker_rows,
        '',
        '## Should fix',
        *warning_rows,
        '',
        '## Minimal release path',
        *sequence_rows,
        '',
        '## Learning-informed items',
        '- Local release templates and known failure patterns were used as advisory signals only.',
        '- These signals do not bypass evidence, checkpoints, blocked zones, or remote-operation protections.',
        '',
        '## Next best action',
        '- Run `agent pr` to prepare a local PR draft, or `agent start "prepare this project for public release"` to continue project work.',
        '',
    ]
    path = release_dir(project) / 'release_readiness_report.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Build local release readiness report.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_release_readiness(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
