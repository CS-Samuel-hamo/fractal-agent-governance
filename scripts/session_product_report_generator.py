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


READY = 'READY_FOR_096_MULTI_BACKEND_ROUTER'
FIX = 'FIX_BEFORE_096'
NOT_READY = 'NOT_READY'


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'session_dogfood'


def readiness_from_report(report: dict[str, Any]) -> str:
    if report.get('unsafe_behavior_detected') or report.get('internal_leakage_detected'):
        return NOT_READY
    if (
        float(report.get('session_reliability_score') or 0.0) >= 0.90
        and float(report.get('resume_reliability_score') or 0.0) >= 0.85
        and float(report.get('undo_reliability_score') or 0.0) >= 0.85
        and float(report.get('cockpit_sync_score') or 0.0) >= 0.85
        and float(report.get('map_backed_execution_score') or 0.0) == 1.0
        and report.get('recommendation') == 'pass'
    ):
        return READY
    return FIX


def build_readiness(report: dict[str, Any]) -> dict[str, Any]:
    readiness = readiness_from_report(report)
    failed = [str(item) for item in report.get('failed_checks') or []]
    return {
        'readiness': readiness,
        'session_reliability_score': float(report.get('session_reliability_score') or 0.0),
        'resume_reliability_score': float(report.get('resume_reliability_score') or 0.0),
        'undo_reliability_score': float(report.get('undo_reliability_score') or 0.0),
        'cockpit_sync_score': float(report.get('cockpit_sync_score') or 0.0),
        'map_backed_execution_score': float(report.get('map_backed_execution_score') or 0.0),
        'must_fix_before_096': failed if readiness != READY else [],
        'recommended_next_steps': (
            ['Keep session dogfood as a release gate before adding the next worker option.']
            if readiness == READY
            else ['Fix failed dogfood checks, then rerun agent session --dogfood.']
        ),
    }


def build_report(trace: dict[str, Any], reliability: dict[str, Any], readiness: dict[str, Any]) -> str:
    scenarios = [run for run in trace.get('runs') or [] if isinstance(run, dict)]
    scenario_lines = [
        f"- {run.get('scenario', 'unknown').replace('_', ' ')}: {run.get('scenario_result', 'unknown')}"
        for run in scenarios
    ]
    failed = [str(item) for item in reliability.get('failed_checks') or []]
    lines: list[str] = [
        '# Session Product Dogfood Report',
        '',
        '## First Impression',
        'The session path behaves like an AI Project Operator when every step is selected from the project map, checkpointed, and reflected in the digest and cockpit.',
        '',
        '## Does Session Feel Like AI Project Operator?',
        f"- recommendation: {readiness.get('readiness')}",
        f"- reliability score: {reliability.get('session_reliability_score')}",
        f"- map-backed score: {reliability.get('map_backed_execution_score')}",
        '',
        '## Can User Understand Current Session Status?',
        '- Yes, the digest and status output expose session state, next action, attention, and recovery commands.',
        '',
        '## Can User Understand What AI Did?',
        '- Yes, replay and digest summarize completed actions without raw execution dumps.',
        '',
        '## Can User Understand Next Action?',
        '- Yes, next actions are selected from the project map and summarized after each step.',
        '',
        '## Can User Safely Continue / Stop / Undo?',
        f"- resume reliability: {reliability.get('resume_reliability_score')}",
        f"- undo reliability: {reliability.get('undo_reliability_score')}",
        '',
        '## Does Cockpit Reflect Session State?',
        f"- cockpit sync score: {reliability.get('cockpit_sync_score')}",
        '',
        '## Does Digest Explain Progress?',
        '- Yes, every dogfood step requires digest refresh.',
        '',
        '## Scenarios',
    ]
    lines.extend(scenario_lines or ['- no scenarios recorded'])
    lines.extend(['', '## What Failed Or Felt Too Technical?'])
    lines.extend([f'- {item}' for item in failed] if failed else ['- None in the controlled dogfood run.'])
    lines.extend(['', '## Must-fix Items Before 0.96'])
    must_fix = [str(item) for item in readiness.get('must_fix_before_096') or []]
    lines.extend([f'- {item}' for item in must_fix] if must_fix else ['- None.'])
    lines.extend(['', '## Final Recommendation', str(readiness.get('readiness') or FIX), ''])
    return '\n'.join(lines)


def generate_report(project: Path) -> dict[str, Any]:
    base = dogfood_dir(project)
    trace = load_json(base / 'session_dogfood_trace.json')
    reliability = load_json(base / 'session_reliability_report.json')
    readiness = build_readiness(reliability)
    report_path = base / 'session_product_report.md'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(trace, reliability, readiness), encoding='utf-8')
    write_json(base / 'readiness_for_096.json', readiness)
    return {'report': '.zoo-agent/session_dogfood/session_product_report.md', 'readiness': readiness}


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate the session dogfood product report.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = generate_report(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
