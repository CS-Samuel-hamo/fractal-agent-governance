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

from cockpit_schema import cockpit_dir, default_cockpit_data  # noqa: E402
from project_logic_rules_check import build_project_logic_rules_check  # noqa: E402
from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


RESTRICTED_RE = re.compile(r'(\.env\b|\.env\.|secret|api\s*key|apikey|token|credential)', re.IGNORECASE)


def clean_text(value: Any) -> str:
    text = str(value or '').replace('\\', '/').strip()
    if not text:
        return ''
    return RESTRICTED_RE.sub('[restricted]', text)


def clean_list(values: Any, *, limit: int = 12) -> list[str]:
    rows: list[str] = []
    if not isinstance(values, list):
        return rows
    for item in values:
        cleaned = clean_text(item)
        if cleaned and cleaned not in rows:
            rows.append(cleaned)
        if len(rows) >= limit:
            break
    return rows


def evidence_count(row: dict[str, Any]) -> int:
    return len([item for item in row.get('evidence') or [] if isinstance(item, dict)])


def project_state_from(session: dict[str, Any], project_map: dict[str, Any], attention: dict[str, Any], readiness: dict[str, Any]) -> str:
    if attention:
        return 'needs_attention'
    status = str(session.get('status') or '').lower()
    if status in {'doing', 'active'}:
        return 'active'
    if status in {'needs_attention'}:
        return 'needs_attention'
    if status in {'stopped', 'paused'}:
        return 'paused'
    if readiness.get('for_094') == 'READY_FOR_094_COCKPIT' or readiness.get('final_recommendation') == 'READY_FOR_094_COCKPIT':
        return 'ready'
    if project_map:
        return 'mapped'
    return 'unknown'


def session_status(session: dict[str, Any], attention: dict[str, Any]) -> str:
    if attention:
        return 'needs_attention'
    raw = str(session.get('status') or '').lower()
    if raw in {'doing', 'active'}:
        return 'active'
    if raw in {'done', 'completed', 'complete'}:
        return 'completed'
    if raw in {'stopped'}:
        return 'stopped'
    if raw in {'paused'}:
        return 'paused'
    return 'not_started'


def build_module_rows(project_map: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in project_map.get('modules') or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                'name': clean_text(item.get('name') or item.get('module_id') or 'module'),
                'status': clean_text(item.get('status') or 'unknown'),
                'confidence': item.get('confidence', 0),
                'key_files': clean_list(item.get('key_files') or []),
                'evidence_count': evidence_count(item),
            }
        )
    return rows


def build_capability_rows(project_map: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in project_map.get('capabilities') or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                'name': clean_text(item.get('name') or item.get('capability_id') or 'capability'),
                'status': clean_text(item.get('status') or 'unknown'),
                'related_modules': clean_list(item.get('related_modules') or []),
                'evidence_count': evidence_count(item),
            }
        )
    return rows


def build_risk_rows(project_map: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in project_map.get('risks') or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                'description': clean_text(item.get('description') or item.get('risk_id') or 'risk'),
                'severity': clean_text(item.get('severity') or 'unknown'),
                'affected_files': clean_list(item.get('affected_files') or []),
                'reason': clean_text((item.get('evidence') or [{}])[0].get('summary') if item.get('evidence') else ''),
            }
        )
    return rows


def mode_for_action(action: dict[str, Any]) -> str:
    explicit = clean_text(action.get('execution_mode'))
    if explicit:
        return explicit
    if str(action.get('risk_level') or '').lower() == 'low' and action.get('autopilot_eligible', True):
        return 'auto'
    if not action.get('autopilot_eligible', True):
        return 'needs_attention'
    return 'preview'


def build_action_rows(project_map: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in project_map.get('next_actions') or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                'action_id': clean_text(item.get('action_id') or ''),
                'title': clean_text(item.get('title') or 'Next action'),
                'why_now': clean_text(item.get('why_now') or 'Not available'),
                'expected_impact': clean_text(item.get('expected_impact') or 'Not available'),
                'risk_level': clean_text(item.get('risk_level') or 'unknown'),
                'target_files': clean_list(item.get('target_files') or []),
                'execution_mode': mode_for_action(item),
                'evidence_count': evidence_count(item),
            }
        )
    return rows


def history_rows(action_history: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in action_history.get('actions') or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                'title': clean_text(item.get('title') or item.get('action_id') or 'Action'),
                'status': clean_text(item.get('status') or item.get('result') or 'unknown'),
                'result': clean_text(item.get('result') or ''),
                'changed_files': clean_list(item.get('changed_files') or []),
                'at': clean_text(item.get('at') or ''),
            }
        )
    return rows


def build_attention(attention: dict[str, Any]) -> dict[str, Any]:
    if not attention:
        return {'requires_attention': False, 'items': []}
    action = attention.get('action') if isinstance(attention.get('action'), dict) else {}
    return {
        'requires_attention': True,
        'items': [
            {
                'reason': clean_text(attention.get('reason') or 'Review required'),
                'suggested_next_step': clean_text(attention.get('suggested_next_step') or 'Review and continue when ready.'),
                'action': clean_text(action.get('title') or action.get('selected_action_id') or ''),
            }
        ],
    }


def build_safety(checkpoints_payload: dict[str, Any]) -> dict[str, Any]:
    checkpoints = [item for item in checkpoints_payload.get('checkpoints') or [] if isinstance(item, dict)]
    latest = checkpoints[-1] if checkpoints else {}
    return {
        'checkpoints_available': bool(checkpoints),
        'undo_available': any(bool(item.get('undo_available')) for item in checkpoints),
        'last_checkpoint': clean_text(latest.get('created_at') or latest.get('checkpoint_id') or ''),
    }


def build_readiness(project: Path) -> dict[str, Any]:
    readiness = load_json(project / '.zoo-agent' / 'dogfood' / 'readiness_for_094.json')
    quality = load_json(project / '.zoo-agent' / 'dogfood' / 'map_quality_report.json')
    return {
        'for_094': clean_text(readiness.get('final_recommendation') or 'not available'),
        'map_quality_score': quality.get('map_quality_score') if quality else None,
        'evidence_coverage': quality.get('evidence_coverage') if quality else None,
    }


def build_worker_summary(project: Path) -> dict[str, Any]:
    routing = load_json(project / '.zoo-agent' / 'workers' / 'routing_decision.json')
    registry = load_json(project / '.zoo-agent' / 'workers' / 'worker_registry.json')
    workers = [item for item in registry.get('workers') or [] if isinstance(item, dict)]
    selected = str(routing.get('selected_worker') or '')
    selected_row = next((item for item in workers if item.get('name') == selected), {})
    role = clean_text(routing.get('worker_role') or selected_row.get('worker_type') or 'not available')
    status = clean_text(selected_row.get('health') or ('available' if selected_row.get('available') else 'not available'))
    return {
        'role': role,
        'status': status,
        'routing_mode': clean_text(routing.get('execution_mode') or 'not available'),
        'reason': clean_text(routing.get('routing_reason') or 'not available'),
        'developer_details': {
            'provider': clean_text(routing.get('selected_provider') or selected_row.get('provider') or ''),
            'worker_name': clean_text(selected),
        },
    }


def product_worker_label(worker: dict[str, Any]) -> str:
    name = str(worker.get('name') or '')
    provider = str(worker.get('provider') or '')
    worker_type = str(worker.get('worker_type') or '')
    if name == 'local_scanner_worker':
        return 'Local Scanner'
    if provider == 'dry_run':
        return 'Dry-run Worker'
    if provider == 'mock':
        return 'Mock Worker'
    if provider == 'codex':
        return 'Code Worker'
    if provider == 'claude':
        return 'Analysis Worker'
    return clean_text(worker.get('role') or worker_type or 'Worker')


def build_worker_readiness(project: Path) -> dict[str, Any]:
    registry = load_json(project / '.zoo-agent' / 'workers' / 'worker_registry.json')
    workers = [item for item in registry.get('workers') or [] if isinstance(item, dict)]
    rows = []
    for item in workers:
        rows.append(
            {
                'role': product_worker_label(item),
                'status': clean_text(item.get('health') or ('ready' if item.get('available') else 'unavailable')),
                'available': bool(item.get('available')),
                'safe_capability': (
                    'actual execution'
                    if item.get('supports_actual_execution')
                    else 'repo scan only'
                    if 'repo_scan' in (item.get('capabilities') or [])
                    else 'preview only'
                    if item.get('supports_preview')
                    else 'unavailable'
                ),
                'developer_details': {
                    'provider': clean_text(item.get('provider') or ''),
                    'worker_name': clean_text(item.get('name') or ''),
                    'reason': clean_text(item.get('reason') or item.get('unavailable_reason') or ''),
                },
            }
        )
    return {
        'workers': rows,
        'actual_execution': 'available' if any(item.get('available') and item.get('supports_actual_execution') and item.get('provider') != 'mock' for item in workers) else 'unavailable',
    }


def product_learning_type(value: str) -> str:
    return {
        'next_action_boost': 'Suggested next action',
        'next_action_warning': 'Common blocker warning',
        'worker_preference': 'Worker preference',
        'readiness_template': 'Release readiness path',
        'failure_warning': 'Failure warning',
    }.get(value, 'Learning insight')


def build_learning_summary(project: Path) -> dict[str, Any]:
    insights_payload = load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'learning_insights.json')
    feedback_payload = load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'learning_feedback_applied.json')
    rows = []
    for item in insights_payload.get('insights') or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                'label': product_learning_type(str(item.get('type') or '')),
                'message': clean_text(item.get('message') or 'Similar project signal is available.'),
                'confidence': item.get('confidence', 0),
                'effect': clean_text(item.get('recommended_effect') or 'suggestion'),
                'evidence_count': len([entry for entry in item.get('evidence') or [] if isinstance(entry, dict)]),
            }
        )
        if len(rows) >= 6:
            break
    return {
        'available': bool(rows),
        'items': rows,
        'feedback_count': len([item for item in feedback_payload.get('applied') or [] if isinstance(item, dict)]),
    }


def build_release_summary(project: Path) -> dict[str, Any]:
    base = project / '.zoo-agent' / 'release'
    git_context = load_json(base / 'git_context.json')
    github_ready = load_json(base / 'github_readiness.json')
    release_ready = load_json(base / 'release_readiness.json')
    pr_plan = load_json(base / 'pr_plan.json')
    action_plan = load_json(base / 'release_action_plan.json')
    workflow = load_json(base / 'readiness_for_0981.json')
    safety = load_json(base / 'github_workflow_safety_report.json')
    available = any((base / name).exists() for name in ['git_context.json', 'release_readiness.json', 'pr_draft.md'])
    blockers = clean_list((github_ready.get('blockers') or []) + (release_ready.get('must_fix') or []), limit=8)
    next_actions = []
    for item in action_plan.get('next_actions') or []:
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get('action') or '')
        if title:
            next_actions.append(title)
        if len(next_actions) >= 5:
            break
    return {
        'available': available,
        'git_status': clean_text(git_context.get('working_tree_status') or 'not available'),
        'branch': clean_text(git_context.get('current_branch') or 'not available'),
        'github_ready': bool(github_ready.get('github_ready')),
        'pr_ready': bool(github_ready.get('pr_ready')),
        'release_ready': bool(github_ready.get('release_ready')),
        'release_stage': clean_text(release_ready.get('stage') or 'not available'),
        'release_score': release_ready.get('readiness_score'),
        'pr_title': clean_text(pr_plan.get('pr_title') or 'not available'),
        'pr_draft_path': '.zoo-agent/release/pr_draft.md' if (base / 'pr_draft.md').exists() else '',
        'release_notes_path': '.zoo-agent/release/release_notes_draft.md' if (base / 'release_notes_draft.md').exists() else '',
        'changelog_path': '.zoo-agent/release/changelog_draft.md' if (base / 'changelog_draft.md').exists() else '',
        'report_path': '.zoo-agent/release/release_workflow_report.md' if (base / 'release_workflow_report.md').exists() else '',
        'blockers': blockers,
        'suggested_next_command': 'agent start "prepare this project for public release"',
        'learning_informed_path': next_actions,
        'safety': 'passed' if safety.get('safe') else 'not available',
        'readiness_for_0981': clean_text(workflow.get('readiness') or 'not available'),
    }


def build_logic_rules_summary(project: Path) -> dict[str, Any]:
    payload = build_project_logic_rules_check(project)
    rules = payload.get('rules') if isinstance(payload.get('rules'), dict) else {}
    logic = payload.get('logic') if isinstance(payload.get('logic'), dict) else {}
    coverage = rules.get('coverage') if isinstance(rules.get('coverage'), dict) else {}
    return {
        'overall_status': clean_text(payload.get('overall_status') or 'unknown'),
        'rules_status': clean_text(rules.get('status') or 'unknown'),
        'workflow_chain': clean_text(logic.get('workflow_chain') or 'unknown'),
        'risk_coverage': clean_text(logic.get('risk_coverage') or 'unknown'),
        'orphan_modules': clean_list(logic.get('orphan_modules') or [], limit=8),
        'missing_links': clean_list(logic.get('missing_links') or [], limit=8),
        'weak_links': clean_list(logic.get('weak_links') or [], limit=8),
        'recommendations': clean_list(logic.get('recommendations') or [], limit=5),
        'coverage': {
            'no_fake_citations': bool(coverage.get('no_fake_citations')),
            'no_fake_results': bool(coverage.get('no_fake_results')),
            'evidence_separation': bool(coverage.get('evidence_separation')),
            'restricted_access': bool(coverage.get('no_secret_access')),
        },
    }


def build_cockpit_data(project: Path) -> dict[str, Any]:
    data = default_cockpit_data(project)
    project_map = load_json(project / '.zoo-agent' / 'map' / 'project_map.json')
    project_state = load_json(project / '.zoo-agent' / 'map' / 'project_state.json')
    session_state = load_json(project / '.zoo-agent' / 'session' / 'session_state.json')
    session = load_json(project / '.zoo-agent' / 'autopilot' / 'session.json')
    progress = load_json(project / '.zoo-agent' / 'autopilot' / 'progress.json')
    action_history = load_json(project / '.zoo-agent' / 'autopilot' / 'action_history.json')
    attention = load_json(project / '.zoo-agent' / 'autopilot' / 'attention_required.json')
    checkpoints = load_json(project / '.zoo-agent' / 'autopilot' / 'checkpoints.json')
    readiness = build_readiness(project)
    history = history_rows(action_history)
    actions = build_action_rows(project_map)

    data['generated_at'] = utc_now()
    combined_session = {**session, **{key: value for key, value in session_state.items() if value not in ['', None]}}
    data['project'] = {
        'name': clean_text(project_map.get('project_name') or project_state.get('project_name') or project.name),
        'type': clean_text(project_map.get('project_type') or 'not available'),
        'main_goal': clean_text(project_map.get('main_goal') or project_state.get('main_goal') or session_state.get('goal') or session.get('goal') or 'not available'),
        'state': project_state_from(combined_session, project_map, attention, readiness),
        'last_updated': clean_text(project_map.get('last_updated') or project_state.get('last_updated') or ''),
    }
    data['session'] = {
        'active': clean_text(session_state.get('status') or session_status(session, attention)) == 'active',
        'goal': clean_text(session_state.get('goal') or session.get('goal') or ''),
        'status': clean_text(session_state.get('status') or session_status(session, attention)),
        'current_action': clean_text(progress.get('title') or ''),
        'last_action': history[-1]['title'] if history else '',
        'next_action': actions[0]['title'] if actions else '',
    }
    data['map'] = {
        'modules': build_module_rows(project_map),
        'capabilities': build_capability_rows(project_map),
        'risks': build_risk_rows(project_map),
        'next_actions': actions,
    }
    data['progress'] = {
        'completed_actions': [item for item in history if item.get('status') in {'done', 'completed', 'preview_ready'}],
        'in_progress_actions': [item for item in history if item.get('status') in {'doing', 'active'}],
        'blocked_actions': [item for item in history if item.get('status') in {'needs_attention', 'blocked', 'failed'}],
        'recent_changes': clean_list([path for item in history[-5:] for path in item.get('changed_files') or []], limit=20),
    }
    data['attention'] = build_attention(attention)
    data['safety'] = build_safety(checkpoints)
    data['readiness'] = readiness
    data['worker'] = build_worker_summary(project)
    data['worker_readiness'] = build_worker_readiness(project)
    data['learning'] = build_learning_summary(project)
    data['release'] = build_release_summary(project)
    data['logic_rules'] = build_logic_rules_summary(project)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description='Build product-level Project Cockpit data.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    data = build_cockpit_data(project)
    output = Path(args.output).resolve() if args.output else cockpit_dir(project) / 'cockpit_data.json'
    write_json(output, data)
    print(json.dumps({'status': 'ok', 'cockpit_data': str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
