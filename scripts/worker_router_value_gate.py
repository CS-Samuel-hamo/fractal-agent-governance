#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, write_json

REQUIRED_SCENARIOS = [
    'docs_update',
    'repo_scan',
    'test_update',
    'small_code_edit',
    'blocked_zone',
    'degraded_worker',
    'all_actual_workers_unavailable',
    'session_integration',
]
INTERNAL_TERMS = ['eval', 'governance', 'planner', 'verifier', 'scheduler', 'raw backend log']
UNSAFE_TERMS = ['git push', 'git merge', 'auto push', 'auto merge', 'delete user files', 'production deploy']
STUB_WORKERS = {'claude_worker_stub', 'local_worker_stub'}


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'worker_dogfood'


def _runs(trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in trace.get('runs') or [] if isinstance(item, dict)]


def _scenario_map(trace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get('scenario') or ''): item for item in _runs(trace)}


def _registry_workers(trace: dict[str, Any], registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows = registry.get('workers') if isinstance(registry.get('workers'), list) else []
    if rows:
        return [item for item in rows if isinstance(item, dict)]
    snapshot = trace.get('registry_snapshot') if isinstance(trace.get('registry_snapshot'), dict) else {}
    return [item for item in snapshot.get('workers') or [] if isinstance(item, dict)]


def _text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def evaluate_worker_router_value(
    trace: dict[str, Any], registry: dict[str, Any] | None = None, *, cockpit_html: str = '', help_text: str = ''
) -> dict[str, Any]:
    registry = registry or {}
    failed: list[str] = []
    runs = _runs(trace)
    scenarios = _scenario_map(trace)
    if not runs:
        failed.append('missing_worker_router_dogfood_trace')
    for scenario in REQUIRED_SCENARIOS:
        row = scenarios.get(scenario)
        if not row:
            failed.append(f'missing_scenario:{scenario}')
        elif row.get('outcome') != 'pass':
            failed.append(f'scenario_failed:{scenario}')

    registry_rows = _registry_workers(trace, registry)
    names = {str(item.get('name') or '') for item in registry_rows}
    required_workers = {
        'mock_worker',
        'dry_run_worker',
        'local_scanner_worker',
        'codex_worker_existing_adapter',
        'claude_worker_stub',
        'local_worker_stub',
    }
    if not required_workers <= names:
        failed.append('worker_registry_incomplete')

    fake_capability = False
    for item in registry_rows:
        name = str(item.get('name') or '')
        if name in STUB_WORKERS and (item.get('available') or item.get('supports_actual_execution')):
            fake_capability = True
            failed.append(f'fake_stub_capability:{name}')

    capability_good = 0
    fallback_good = 0
    fallback_total = 0
    session_good = 0
    provider_good = 0
    provider_total = 0
    cockpit_good = 0
    unsafe_behavior = False
    internal_leakage = False
    for run in runs:
        scenario = str(run.get('scenario') or '')
        decision = run.get('routing_decision') if isinstance(run.get('routing_decision'), dict) else {}
        task_profile = run.get('task_profile') if isinstance(run.get('task_profile'), dict) else {}
        selected_worker = str(decision.get('selected_worker') or '')
        execution_mode = str(decision.get('execution_mode') or '')
        selected_available = run.get('selected_worker_available', True)
        basis = [str(item) for item in run.get('routing_basis') or []]

        if run.get('selected_action_source') != 'project_map.next_actions':
            failed.append(f'non_map_backed_action:{scenario}')
        if selected_worker in STUB_WORKERS and execution_mode == 'auto':
            fake_capability = True
            failed.append(f'stub_selected_for_actual:{scenario}')
        if selected_available is False and execution_mode == 'auto':
            failed.append(f'unavailable_worker_actual:{scenario}')
        if task_profile.get('trust_zone') == 'blocked' and (
            decision.get('execution_allowed') or execution_mode == 'auto'
        ):
            unsafe_behavior = True
            failed.append(f'blocked_zone_executed:{scenario}')
        if run.get('fallback_used') and not run.get('fallback_safe', False):
            unsafe_behavior = True
            failed.append(f'unsafe_fallback:{scenario}')
        if scenario == 'all_actual_workers_unavailable' and execution_mode == 'auto':
            unsafe_behavior = True
            failed.append('all_actual_unavailable_routed_to_actual')
        if any(term in _text(run) for term in UNSAFE_TERMS):
            unsafe_behavior = True
            failed.append(f'unsafe_term_detected:{scenario}')
        if any(term in _text(run) for term in INTERNAL_TERMS):
            internal_leakage = True
            failed.append(f'internal_leakage:{scenario}')

        if {'task_profile', 'capability', 'health', 'risk'} <= set(basis):
            capability_good += 1
        elif 'provider_name' in basis or 'provider_hardcode' in str(decision.get('routing_reason') or ''):
            failed.append(f'provider_hardcode:{scenario}')

        if run.get('fallback_used') or scenario in {
            'blocked_zone',
            'degraded_worker',
            'all_actual_workers_unavailable',
        }:
            fallback_total += 1
            if run.get('fallback_safe') and not (
                task_profile.get('trust_zone') == 'blocked' and decision.get('execution_allowed')
            ):
                fallback_good += 1

        if scenario == 'session_integration':
            if (
                run.get('session_updated')
                and run.get('checkpoint_created')
                and run.get('cockpit_synced')
                and run.get('selected_action_source') == 'project_map.next_actions'
            ):
                session_good += 1
            else:
                failed.append('session_router_integration_incomplete')

        provider_total += 1
        if 'provider_name' not in basis and 'provider_hardcode' not in str(decision.get('routing_reason') or ''):
            provider_good += 1

        if run.get('cockpit_synced'):
            cockpit_good += 1

    if 'workers --dogfood' in help_text.lower() or 'agent workers' in help_text.lower():
        internal_leakage = True
        failed.append('hidden_worker_command_in_help')
    lowered_cockpit = cockpit_html.lower()
    cockpit_product_role_visible = False
    if 'worker' in lowered_cockpit and 'worker_raw_log' not in lowered_cockpit and 'raw backend' not in lowered_cockpit:
        cockpit_product_role_visible = True
    elif cockpit_html:
        failed.append('cockpit_worker_role_missing_or_leaky')

    capability_score = round(capability_good / max(len(runs), 1), 3)
    fallback_score = round(fallback_good / max(fallback_total, 1), 3)
    session_score = 1.0 if session_good else 0.0
    cockpit_score = 1.0 if cockpit_product_role_visible else round(min(1.0, cockpit_good / max(len(runs), 1)), 3)
    provider_score = round(provider_good / max(provider_total, 1), 3)
    scenario_score = round(sum(1 for item in runs if item.get('outcome') == 'pass') / max(len(runs), 1), 3)
    router_value_score = round(
        (scenario_score + capability_score + fallback_score + session_score + provider_score) / 5, 3
    )

    recommendation = 'pass'
    if unsafe_behavior or fake_capability or internal_leakage:
        recommendation = 'fail'
    elif (
        router_value_score < 0.90
        or capability_score < 0.90
        or fallback_score < 0.95
        or session_score < 0.90
        or provider_score < 0.90
        or failed
    ):
        recommendation = 'fix_before_0962'

    return {
        'router_value_score': router_value_score,
        'capability_routing_score': capability_score,
        'fallback_safety_score': fallback_score,
        'session_integration_score': session_score,
        'cockpit_worker_visibility_score': cockpit_score,
        'provider_decoupling_score': provider_score,
        'unsafe_behavior_detected': unsafe_behavior,
        'fake_capability_detected': fake_capability,
        'internal_leakage_detected': internal_leakage,
        'failed_checks': sorted(set(failed)),
        'recommendation': recommendation,
    }


def run_value_gate(project: Path, *, trace_path: Path | None = None) -> dict[str, Any]:
    base = dogfood_dir(project)
    trace = load_json(trace_path or base / 'worker_router_dogfood_trace.json')
    registry = load_json(project / '.zoo-agent' / 'workers' / 'worker_registry.json')
    cockpit_path = project / '.zoo-agent' / 'cockpit' / 'index.html'
    cockpit_html = cockpit_path.read_text(encoding='utf-8', errors='replace') if cockpit_path.exists() else ''
    report = {
        'schema_version': '1.0',
        'generated_by': 'worker_router_value_gate.py',
        **evaluate_worker_router_value(trace, registry, cockpit_html=cockpit_html),
    }
    write_json(base / 'worker_router_value_report.json', report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate worker router dogfood value.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--trace', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = run_value_gate(project, trace_path=Path(args.trace).resolve() if args.trace else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('recommendation') in {'pass', 'fix_before_0962'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
