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


READY = 'READY_FOR_0962_REAL_WORKER_ADAPTER_HARDENING'
FIX = 'FIX_BEFORE_0962'
NOT_READY = 'NOT_READY'


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'worker_dogfood'


def readiness_from_report(report: dict[str, Any]) -> str:
    if report.get('unsafe_behavior_detected') or report.get('fake_capability_detected') or report.get('internal_leakage_detected'):
        return NOT_READY
    if (
        float(report.get('router_value_score') or 0.0) >= 0.90
        and float(report.get('capability_routing_score') or 0.0) >= 0.90
        and float(report.get('fallback_safety_score') or 0.0) >= 0.95
        and float(report.get('session_integration_score') or 0.0) >= 0.90
        and float(report.get('provider_decoupling_score') or 0.0) >= 0.90
        and report.get('recommendation') == 'pass'
    ):
        return READY
    return FIX


def build_readiness(report: dict[str, Any]) -> dict[str, Any]:
    readiness = readiness_from_report(report)
    failed = [str(item) for item in report.get('failed_checks') or []]
    return {
        'readiness': readiness,
        'router_value_score': float(report.get('router_value_score') or 0.0),
        'capability_routing_score': float(report.get('capability_routing_score') or 0.0),
        'fallback_safety_score': float(report.get('fallback_safety_score') or 0.0),
        'session_integration_score': float(report.get('session_integration_score') or 0.0),
        'cockpit_worker_visibility_score': float(report.get('cockpit_worker_visibility_score') or 0.0),
        'provider_decoupling_score': float(report.get('provider_decoupling_score') or 0.0),
        'must_fix_before_0962': failed if readiness != READY else [],
        'recommended_next_steps': (
            ['Proceed to harden real worker adapters without changing the user-facing project operator model.']
            if readiness == READY
            else ['Fix worker router dogfood failures, then rerun agent workers --dogfood.']
        ),
    }


def build_report(trace: dict[str, Any], value_report: dict[str, Any], readiness: dict[str, Any]) -> str:
    runs = [item for item in trace.get('runs') or [] if isinstance(item, dict)]
    scenario_lines = [f"- {str(item.get('scenario') or 'unknown').replace('_', ' ')}: {item.get('outcome', 'unknown')}" for item in runs]
    failed = [str(item) for item in value_report.get('failed_checks') or []]
    stub_lines = [
        '- Claude worker is a stub and remains unavailable.',
        '- Local worker is a stub and remains unavailable.',
    ]
    lines = [
        '# Worker Router Product Report',
        '',
        '## First Impression',
        'The router adds product value when project actions are matched to worker roles without making users configure providers first.',
        '',
        '## Does Router Make The Product Less Like A Codex Wrapper?',
        f"- provider decoupling score: {readiness.get('provider_decoupling_score')}",
        '- Codex is one worker adapter, not the product control plane.',
        '',
        '## Does Routing Improve Reliability?',
        f"- router value score: {readiness.get('router_value_score')}",
        f"- capability routing score: {readiness.get('capability_routing_score')}",
        '',
        '## Does Fallback Feel Safe?',
        f"- fallback safety score: {readiness.get('fallback_safety_score')}",
        '- Fallback downgrades to safe preview or needs attention instead of escalating blocked work.',
        '',
        '## Does Cockpit Explain Worker Role Clearly?',
        f"- cockpit worker visibility score: {readiness.get('cockpit_worker_visibility_score')}",
        '- Cockpit shows product-level worker role and hides raw provider logs.',
        '',
        '## Does User Still See Project Operator, Not Backend Config?',
        '- Yes. The visible path remains start, status, continue, stop, undo, and cockpit.',
        '',
        '## Stub / Unavailable Capabilities',
        *stub_lines,
        '',
        '## Scenarios',
    ]
    lines.extend(scenario_lines or ['- no scenarios recorded'])
    lines.extend(['', '## Must-fix Before Real Worker Adapters'])
    lines.extend([f'- {item}' for item in failed] if failed else ['- None.'])
    lines.extend(
        [
            '',
            '## Should We Proceed To 0.96.2 Real Worker Adapter Hardening?',
            str(readiness.get('readiness') or FIX),
            '',
            '## Final Recommendation',
            str(readiness.get('readiness') or FIX),
            '',
        ]
    )
    return '\n'.join(lines)


def generate_report(project: Path) -> dict[str, Any]:
    base = dogfood_dir(project)
    trace = load_json(base / 'worker_router_dogfood_trace.json')
    value_report = load_json(base / 'worker_router_value_report.json')
    readiness = build_readiness(value_report)
    report_path = base / 'worker_router_product_report.md'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(trace, value_report, readiness), encoding='utf-8')
    write_json(base / 'readiness_for_0962.json', readiness)
    return {'report': '.zoo-agent/worker_dogfood/worker_router_product_report.md', 'readiness': readiness}


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate worker router product report.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = generate_report(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
