#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_map_builder import build_project_map
from project_map_schema import map_dir
from runtime_common import load_json, project_root, utc_now, write_json
from seed_prompt_discovery import (
    discover_seed_prompt,
    intent_first_bootstrap_enabled,
    is_research_seed,
    seed_evidence_item,
)
from trust_zone_classifier import classify_trust_zone

DANGEROUS_GOAL_TERMS = [
    'delete',
    'remove files',
    'wipe',
    'read .env',
    '.env',
    'secret',
    'api key',
    'token',
    'credential',
    'password',
    'git push',
    'push to github',
    'merge',
    'production deploy',
    'deploy production',
    'database migration',
]


def action_history(project: Path) -> list[dict[str, Any]]:
    payload = load_json(project / '.zoo-agent' / 'autopilot' / 'action_history.json')
    return [item for item in payload.get('actions') or [] if isinstance(item, dict)]


def _score(action: dict[str, Any], seen: set[str], seen_files: set[str]) -> float:
    score = 0.0
    if action.get('autopilot_eligible'):
        score += 2.0
    if action.get('risk_level') == 'low':
        score += 2.0
    if action.get('target_files'):
        score += 1.0
    if action.get('evidence'):
        score += 1.0
    if action.get('source') == 'seed_prompt' or action.get('action_type') == 'create_or_preview_docs':
        score += 1.0
    if str(action.get('action_id')) in seen:
        score -= 4.0
    targets = {str(item).replace('\\', '/') for item in action.get('target_files') or []}
    if targets & seen_files:
        score -= 3.0
    title = str(action.get('title') or '').lower()
    if any(word in title for word in ['readme', 'docs', 'test']):
        score += 0.5
    return score


def learning_score(project: Path, action: dict[str, Any]) -> float:
    insights = (
        load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'learning_insights.json').get('insights')
        or []
    )
    title = str(action.get('title') or '').lower()
    boost = 0.0
    for item in insights:
        if not isinstance(item, dict):
            continue
        effect = str(item.get('recommended_effect') or '')
        confidence = float(item.get('confidence') or 0.0)
        applies_to = str(item.get('applies_to') or '').lower()
        message = str(item.get('message') or '').lower()
        if (
            effect == 'boost'
            and confidence >= 0.5
            and (
                applies_to in title
                or any(word in title for word in ['docs', 'readme', 'test', 'scan', 'release'] if word in message)
            )
        ):
            boost += min(1.5, confidence)
        if effect in {'warn', 'deprioritize'} and applies_to and applies_to in title:
            boost -= min(1.0, max(0.2, confidence))
    return boost


def action_is_autopilot_ready(action: dict[str, Any]) -> bool:
    return bool(
        action.get('autopilot_eligible')
        and action.get('why_now')
        and action.get('target_files')
        and action.get('expected_impact')
        and action.get('evidence')
    )


def _goal_intent_evidence(goal: str) -> dict[str, Any]:
    return {
        'kind': 'user_goal_intent',
        'evidence_type': 'user_goal_intent',
        'path': '<user goal>',
        'summary': goal[:360] or 'User provided a project goal.',
        'confidence': 0.58,
        'trust_level': 'user_intent_evidence',
        'safety_checked': True,
    }


def _starter_targets(seed_evidence: dict[str, Any] | None, goal: str) -> list[str]:
    targets = ['README.md', 'docs/project_plan.md']
    if seed_evidence and seed_evidence.get('research_seed'):
        targets.append('docs/research_workflow.md')
    elif is_research_seed(str((seed_evidence or {}).get('summary') or ''), goal):
        targets.append('docs/research_workflow.md')
    return targets


def _existing_targets(project: Path, targets: list[str]) -> list[str]:
    return [target for target in targets if (project / target).exists()]


def _starter_action_from_evidence(project: Path, *, evidence: dict[str, Any], goal: str, source: str) -> dict[str, Any]:
    targets = _starter_targets(evidence, goal)
    existing = _existing_targets(project, targets)
    missing = [target for target in targets if target not in existing]
    all_targets_exist = bool(targets) and not missing
    return {
        'schema_version': '1.0',
        'generated_by': 'map_task_selector.py',
        'generated_at': utc_now(),
        'selected_action_id': 'action-seed-docs-bootstrap'
        if source == 'seed_prompt'
        else 'action-intent-docs-bootstrap',
        'action_id': 'action-seed-docs-bootstrap' if source == 'seed_prompt' else 'action-intent-docs-bootstrap',
        'title': 'Create starter project documents from seed prompt'
        if source == 'seed_prompt'
        else 'Create starter project plan from goal',
        'reason': 'Fallback activated from seed prompt.'
        if source == 'seed_prompt'
        else 'Fallback activated from user goal because no map-backed action was available.',
        'expected_project_progress': 'Creates a trusted documentation starting point without running scripts.',
        'risk_level': 'low',
        'target_files': targets,
        'execution_mode': 'preview' if all_targets_exist else 'auto',
        'trust_zone': 'trusted',
        'trust_zone_reasons': ['trusted_documentation_test_example_or_local_script_surface'],
        'source': source,
        'source_file': evidence.get('path', '') if source == 'seed_prompt' else '',
        'action_type': 'create_or_preview_docs',
        'project_map_ref': str(map_dir(project) / 'project_map.json'),
        'evidence': [evidence],
        'autopilot_eligible': True,
        'preview_only': all_targets_exist,
        'preview_reason': 'all starter docs already exist; no overwrite' if all_targets_exist else '',
        'existing_targets': existing,
        'missing_targets': missing,
        'constraints': ['trusted_docs_only', 'no_script_execution', 'no_secret_access', 'no_overwrite'],
        'safety_constraints': [
            'trusted_docs_only',
            'no_script_execution',
            'no_secret_access',
            'no_external_network',
            'no_fake_citations',
            'no_final_paper_generation',
        ],
        'fallback_behavior': {
            'if_target_exists': 'skip_existing_create_missing',
            'if_all_targets_exist': 'preview_only',
            'if_ambiguous_intent': 'present_options',
        },
        'learning_feedback_ref': '.zoo-agent/learning/cross_project/learning_insights.json',
    }


def _dangerous_goal_reason(goal: str) -> str:
    surface = goal.lower()
    for term in DANGEROUS_GOAL_TERMS:
        if term in surface:
            return f'dangerous goal requires review: {term}'
    return ''


def _intent_first_fallback(project: Path, *, goal: str) -> dict[str, Any]:
    dangerous = _dangerous_goal_reason(goal)
    if dangerous:
        payload = {
            'schema_version': '1.0',
            'generated_by': 'map_task_selector.py',
            'generated_at': utc_now(),
            'selected_action_id': '',
            'reason': dangerous,
            'expected_project_progress': 'none',
            'risk_level': 'high',
            'target_files': [],
            'execution_mode': 'needs_attention',
            'trust_zone': 'blocked',
            'blocked_reason': dangerous,
            'source': 'intent_first_fallback',
        }
        write_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json', payload)
        return payload

    seed_report = discover_seed_prompt(project, goal=goal)
    selected_seed = seed_report.get('selected') if isinstance(seed_report.get('selected'), dict) else None
    if selected_seed:
        payload = _starter_action_from_evidence(
            project, evidence=seed_evidence_item(selected_seed), goal=goal, source='seed_prompt'
        )
        write_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json', payload)
        return payload

    if goal.strip():
        payload = _starter_action_from_evidence(
            project, evidence=_goal_intent_evidence(goal), goal=goal, source='user_goal'
        )
        write_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json', payload)
        return payload

    payload = {
        'schema_version': '1.0',
        'generated_by': 'map_task_selector.py',
        'generated_at': utc_now(),
        'selected_action_id': '',
        'title': 'Clarify project starting goal',
        'reason': 'No executable Project Map-backed next action and no useful project intent were found.',
        'expected_project_progress': 'none',
        'risk_level': 'unknown',
        'target_files': [],
        'execution_mode': 'needs_attention',
        'trust_zone': 'guarded',
        'blocked_reason': 'missing project intent',
        'source': 'intent_first_fallback',
    }
    write_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json', payload)
    return payload


def select_next_action(project: Path, *, mode: str = 'standard') -> dict[str, Any]:
    map_path = map_dir(project) / 'project_map.json'
    project_map = load_json(map_path)
    if not project_map:
        project_map, state, evidence = build_project_map(project)
        write_json(map_dir(project) / 'project_map.json', project_map)
        write_json(map_dir(project) / 'project_state.json', state)
        write_json(map_dir(project) / 'map_evidence.json', evidence)

    actions = [item for item in project_map.get('next_actions') or [] if isinstance(item, dict)]
    ready_actions = [item for item in actions if action_is_autopilot_ready(item)]
    history = action_history(project)
    seen = {str(item.get('action_id') or item.get('selected_action_id') or '') for item in history}
    seen_files = {str(path).replace('\\', '/') for item in history for path in (item.get('target_files') or [])}
    if not ready_actions:
        if intent_first_bootstrap_enabled():
            goal = str(project_map.get('main_goal') or '')
            return _intent_first_fallback(project, goal=goal)
        payload = {
            'schema_version': '1.0',
            'generated_by': 'map_task_selector.py',
            'generated_at': utc_now(),
            'selected_action_id': '',
            'reason': 'no_executable_map_backed_next_action_available',
            'expected_project_progress': 'none',
            'risk_level': 'unknown',
            'target_files': [],
            'execution_mode': 'needs_attention',
            'trust_zone': 'blocked',
        }
        write_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json', payload)
        return payload

    selected = sorted(
        ready_actions, key=lambda item: _score(item, seen, seen_files) + learning_score(project, item), reverse=True
    )[0]
    trust = classify_trust_zone(
        title=str(selected.get('title') or ''),
        target_files=[str(item) for item in selected.get('target_files') or []],
        risk_level=str(selected.get('risk_level') or 'unknown'),
    )
    if mode == 'preview':
        execution_mode = 'preview'
    elif selected.get('preview_only'):
        execution_mode = 'preview'
    elif mode == 'autopilot':
        execution_mode = trust.get('autopilot_mode')
    else:
        execution_mode = trust.get('standard_mode')
    payload = {
        'schema_version': '1.0',
        'generated_by': 'map_task_selector.py',
        'generated_at': utc_now(),
        'selected_action_id': selected.get('action_id', ''),
        'title': selected.get('title', ''),
        'reason': selected.get('why_now', ''),
        'expected_project_progress': selected.get('expected_impact', ''),
        'risk_level': selected.get('risk_level', 'unknown'),
        'target_files': selected.get('target_files') or [],
        'execution_mode': execution_mode,
        'trust_zone': trust.get('zone'),
        'trust_zone_reasons': trust.get('reasons') or [],
        'source': 'project_map.next_actions',
        'action_source': selected.get('source', ''),
        'source_file': selected.get('source_file', ''),
        'action_type': selected.get('action_type', ''),
        'evidence': selected.get('evidence') or [],
        'autopilot_eligible': bool(selected.get('autopilot_eligible')),
        'preview_only': bool(selected.get('preview_only')),
        'preview_reason': selected.get('preview_reason', ''),
        'existing_targets': selected.get('existing_targets') or [],
        'missing_targets': selected.get('missing_targets') or [],
        'fallback_behavior': selected.get('fallback_behavior') or {},
        'constraints': selected.get('constraints') or [],
        'safety_constraints': selected.get('safety_constraints') or [],
        'project_map_ref': str(map_path),
        'learning_feedback_ref': '.zoo-agent/learning/cross_project/learning_insights.json',
    }
    write_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Select the next project-map-backed action.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='standard')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = select_next_action(project, mode=args.mode)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
