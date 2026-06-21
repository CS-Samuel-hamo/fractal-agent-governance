#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, write_json  # noqa: E402


REQUIRED_SCENARIOS = [
    'worker_doctor',
    'local_scanner_repo_scan',
    'project_map_support',
    'session_with_real_worker_availability',
    'codex_unavailable_graceful_degrade',
    'claude_detection_no_fake_actual',
    'cockpit_worker_readiness',
]
INTERNAL_TERMS = ['eval', 'governance', 'planner', 'verifier', 'scheduler', 'raw backend log']
SECRET_MARKERS = ['api_key=', 'api key=', 'secret=', 'token=', 'should-not-be-read', '.env content']
UNSAFE_TERMS = ['git push', 'git merge', 'auto push', 'auto merge', 'delete user files', 'production deploy']


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'real_worker_dogfood'


def rows(trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in trace.get('runs') or [] if isinstance(item, dict)]


def scenario_map(trace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get('scenario') or ''): item for item in rows(trace)}


def text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def score_ratio(good: int, total: int) -> float:
    return round(good / max(total, 1), 3)


def evaluate_real_worker_value(
    trace: dict[str, Any],
    *,
    doctor: dict[str, Any] | None = None,
    environment_report: str = '',
    scanner_report: dict[str, Any] | None = None,
    codex_health: dict[str, Any] | None = None,
    claude_detection: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
    routing_decision: dict[str, Any] | None = None,
    cockpit_html: str = '',
    project_map: dict[str, Any] | None = None,
    map_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doctor = doctor or {}
    scanner_report = scanner_report or {}
    codex_health = codex_health or {}
    claude_detection = claude_detection or {}
    registry = registry or {}
    routing_decision = routing_decision or {}
    project_map = project_map or {}
    map_evidence = map_evidence or {}
    failed: list[str] = []
    unsafe = False
    fake = False
    secret_read = False
    internal = False
    scenario_rows = scenario_map(trace)

    for scenario in REQUIRED_SCENARIOS:
        row = scenario_rows.get(scenario)
        if not row:
            failed.append(f'missing_scenario:{scenario}')
        elif row.get('outcome') != 'pass':
            failed.append(f'scenario_failed:{scenario}')

    all_text = '\n'.join([text(trace), text(doctor), environment_report.lower(), text(scanner_report), text(registry), text(routing_decision), cockpit_html.lower(), text(project_map), text(map_evidence)])
    if any(marker in all_text for marker in SECRET_MARKERS):
        secret_read = True
        failed.append('secret_content_marker_detected')
    if any(term in all_text for term in INTERNAL_TERMS):
        internal = True
        failed.append('internal_leakage_detected')
    if any(term in all_text for term in UNSAFE_TERMS):
        unsafe = True
        failed.append('unsafe_behavior_text_detected')

    workers = [item for item in registry.get('workers') or [] if isinstance(item, dict)]
    worker_names = {str(item.get('name') or '') for item in workers}
    if not {'local_scanner_worker', 'dry_run_worker', 'mock_worker', 'codex_worker_existing_adapter', 'claude_worker_stub'} <= worker_names:
        failed.append('registry_missing_required_workers')
    for worker in workers:
        if worker.get('name') in {'claude_worker_stub', 'local_worker_stub'} and worker.get('supports_actual_execution'):
            fake = True
            failed.append(f"fake_actual_capability:{worker.get('name')}")

    doctor_score = 1.0
    if not doctor.get('workers') or not environment_report.strip():
        doctor_score = 0.0
        failed.append('worker_doctor_missing_report')
    elif 'Workers:' not in environment_report and '# Worker Environment Report' not in environment_report:
        doctor_score = 0.6
        failed.append('worker_doctor_not_human_readable')

    scanner_good = 0
    if scanner_report.get('files_scanned', 0) > 0:
        scanner_good += 1
    else:
        failed.append('local_scanner_scanned_no_files')
    if scanner_report.get('map_support', {}).get('evidence'):
        scanner_good += 1
    else:
        failed.append('local_scanner_missing_map_evidence')
    skipped_text = text(scanner_report.get('files_skipped') or [])
    if '.env' in skipped_text or 'secret' in skipped_text:
        scanner_good += 1
    else:
        failed.append('local_scanner_no_restricted_skip_evidence')
    local_scanner_score = score_ratio(scanner_good, 3)

    graceful_good = 0
    codex_unavailable = codex_health.get('health') in {'unavailable', 'degraded'} or codex_health.get('available') is False
    codex_row = scenario_rows.get('codex_unavailable_graceful_degrade', {})
    if codex_unavailable and codex_row.get('outcome') == 'pass':
        graceful_good += 1
    elif not codex_unavailable:
        graceful_good += 1
    else:
        failed.append('codex_unavailable_not_graceful')
    if not any(row.get('worker_environment', {}).get('codex') == 'fatal' for row in rows(trace)):
        graceful_good += 1
    else:
        failed.append('codex_fatal_behavior_detected')
    fallback_rows = [row for row in rows(trace) if row.get('fallback_used') or row.get('execution_mode') in {'dry_run', 'needs_attention', 'preview'}]
    if all(row.get('unsafe_behavior_detected') is False for row in fallback_rows):
        graceful_good += 1
    else:
        unsafe = True
        failed.append('unsafe_fallback_detected')
    graceful_score = score_ratio(graceful_good, 3)

    no_fake_score = 1.0
    if claude_detection.get('supports_actual_execution') is not False:
        fake = True
        no_fake_score = 0.0
        failed.append('claude_actual_execution_faked')
    for row in rows(trace):
        if row.get('fake_capability_detected'):
            fake = True
            no_fake_score = 0.0
            failed.append(f"fake_capability:{row.get('scenario')}")
        if row.get('unsafe_behavior_detected'):
            unsafe = True
            failed.append(f"unsafe_behavior:{row.get('scenario')}")

    operator_good = 0
    if scenario_rows.get('session_with_real_worker_availability', {}).get('session_updated'):
        operator_good += 1
    else:
        failed.append('session_not_updated')
    if scenario_rows.get('project_map_support', {}).get('project_map_supported') and (project_map.get('modules') or map_evidence.get('evidence') or scanner_report.get('map_support', {}).get('evidence')):
        operator_good += 1
    else:
        failed.append('project_map_not_scanner_supported')
    if 'Project Operator' in environment_report or 'AI Project Operator' in environment_report or trace.get('product_positioning') == 'AI Project Operator':
        operator_good += 1
    else:
        failed.append('project_operator_positioning_missing')
    operator_score = score_ratio(operator_good, 3)

    cockpit_score = 1.0 if 'Worker Readiness' in cockpit_html and 'raw backend' not in cockpit_html.lower() else 0.0
    if cockpit_score < 1.0:
        failed.append('cockpit_worker_readiness_missing_or_leaky')

    scenario_score = score_ratio(sum(1 for row in rows(trace) if row.get('outcome') == 'pass'), len(REQUIRED_SCENARIOS))
    real_worker_value = round((scenario_score + doctor_score + local_scanner_score + graceful_score + no_fake_score + operator_score + cockpit_score) / 7, 3)

    recommendation = 'pass'
    if unsafe or fake or secret_read or internal:
        recommendation = 'fail'
    elif (
        real_worker_value < 0.90
        or doctor_score < 0.90
        or local_scanner_score < 0.90
        or graceful_score < 0.95
        or no_fake_score < 1.0
        or operator_score < 0.90
        or cockpit_score < 0.90
        or failed
    ):
        recommendation = 'fix_before_097'

    return {
        'real_worker_value_score': real_worker_value,
        'worker_doctor_score': doctor_score,
        'local_scanner_value_score': local_scanner_score,
        'graceful_degradation_score': graceful_score,
        'no_fake_capability_score': no_fake_score,
        'project_operator_positioning_score': operator_score,
        'cockpit_readiness_score': cockpit_score,
        'unsafe_behavior_detected': unsafe,
        'fake_capability_detected': fake,
        'secret_read_detected': secret_read,
        'internal_leakage_detected': internal,
        'failed_checks': sorted(set(failed)),
        'recommendation': recommendation,
    }


def run_value_gate(project: Path, *, trace_path: Path | None = None) -> dict[str, Any]:
    base = dogfood_dir(project)
    trace = load_json(trace_path or base / 'real_worker_dogfood_trace.json')
    cockpit = project / '.zoo-agent' / 'cockpit' / 'index.html'
    environment = project / '.zoo-agent' / 'workers' / 'worker_environment_report.md'
    report = {
        'schema_version': '1.0',
        'generated_by': 'real_worker_value_gate.py',
        **evaluate_real_worker_value(
            trace,
            doctor=load_json(project / '.zoo-agent' / 'workers' / 'worker_doctor_report.json'),
            environment_report=environment.read_text(encoding='utf-8', errors='replace') if environment.exists() else '',
            scanner_report=load_json(project / '.zoo-agent' / 'workers' / 'local_scanner_report.json'),
            codex_health=load_json(project / '.zoo-agent' / 'workers' / 'codex_adapter_health.json'),
            claude_detection=load_json(project / '.zoo-agent' / 'workers' / 'claude_code_detection.json'),
            registry=load_json(project / '.zoo-agent' / 'workers' / 'worker_registry.json'),
            routing_decision=load_json(project / '.zoo-agent' / 'workers' / 'routing_decision.json'),
            cockpit_html=cockpit.read_text(encoding='utf-8', errors='replace') if cockpit.exists() else '',
            project_map=load_json(project / '.zoo-agent' / 'map' / 'project_map.json'),
            map_evidence=load_json(project / '.zoo-agent' / 'map' / 'map_evidence.json'),
        ),
    }
    write_json(base / 'real_worker_value_report.json', report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate real worker adapter dogfood value.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--trace', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = run_value_gate(project, trace_path=Path(args.trace).resolve() if args.trace else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('recommendation') in {'pass', 'fix_before_097'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
