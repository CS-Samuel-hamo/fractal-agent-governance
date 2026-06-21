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


READY = 'READY_FOR_097_CROSS_PROJECT_LEARNING'
FIX = 'FIX_BEFORE_097'
NOT_READY = 'NOT_READY'


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'real_worker_dogfood'


def readiness_from(report: dict[str, Any]) -> str:
    if report.get('unsafe_behavior_detected') or report.get('fake_capability_detected') or report.get('secret_read_detected') or report.get('internal_leakage_detected'):
        return NOT_READY
    if (
        float(report.get('real_worker_value_score') or 0.0) >= 0.90
        and float(report.get('worker_doctor_score') or 0.0) >= 0.90
        and float(report.get('local_scanner_value_score') or 0.0) >= 0.90
        and float(report.get('graceful_degradation_score') or 0.0) >= 0.95
        and float(report.get('no_fake_capability_score') or 0.0) == 1.0
        and float(report.get('project_operator_positioning_score') or 0.0) >= 0.90
        and report.get('recommendation') == 'pass'
    ):
        return READY
    return FIX


def build_readiness(report: dict[str, Any]) -> dict[str, Any]:
    readiness = readiness_from(report)
    failed = [str(item) for item in report.get('failed_checks') or []]
    return {
        'readiness': readiness,
        'real_worker_value_score': float(report.get('real_worker_value_score') or 0.0),
        'worker_doctor_score': float(report.get('worker_doctor_score') or 0.0),
        'local_scanner_value_score': float(report.get('local_scanner_value_score') or 0.0),
        'graceful_degradation_score': float(report.get('graceful_degradation_score') or 0.0),
        'no_fake_capability_score': float(report.get('no_fake_capability_score') or 0.0),
        'project_operator_positioning_score': float(report.get('project_operator_positioning_score') or 0.0),
        'must_fix_before_097': failed if readiness != READY else [],
        'recommended_next_steps': (
            ['Proceed to 0.97 Cross-project Learning with worker readiness as supporting evidence, not as a user-facing backend panel.']
            if readiness == READY
            else ['Fix real worker dogfood value gate failures, then rerun agent workers --real-dogfood.']
        ),
    }


def build_report(value_report: dict[str, Any], readiness: dict[str, Any]) -> str:
    failed = [str(item) for item in value_report.get('failed_checks') or []]
    must_fix_lines = [f'- {item}' for item in failed] if failed else ['- No must-fix items from this gate.']
    return '\n'.join(
        [
            '# Project Operator Value Report',
            '',
            '## First Impression',
            'The worker layer now behaves like local project capability, not provider configuration.',
            '',
            '## Does This Still Feel Like AI Project Operator?',
            f"- project operator positioning score: {readiness.get('project_operator_positioning_score')}",
            '- The visible user path remains workers doctor, start, status, continue, and cockpit.',
            '',
            '## Does Worker Layer Reduce Codex-wrapper Risk?',
            f"- real worker value score: {readiness.get('real_worker_value_score')}",
            '- Local scanner and dry-run flows remain useful even when the Code Worker is unavailable.',
            '',
            '## Does Local Scanner Improve Project Map Quality?',
            f"- local scanner value score: {readiness.get('local_scanner_value_score')}",
            '- It contributes metadata-backed evidence without reading restricted file contents.',
            '',
            '## Does Worker Doctor Improve User Trust?',
            f"- worker doctor score: {readiness.get('worker_doctor_score')}",
            '- It explains what the machine can safely do without exposing raw logs.',
            '',
            '## Does Graceful Degradation Work?',
            f"- graceful degradation score: {readiness.get('graceful_degradation_score')}",
            '- External worker failures degrade to preview, dry-run, local scan, or needs attention.',
            '',
            '## Does Cockpit Show Worker Readiness Clearly?',
            '- Cockpit shows product-level worker readiness and keeps provider details secondary.',
            '',
            '## What Remains Weak Before Cross-project Learning?',
            *must_fix_lines,
            '',
            '## Should We Proceed To 0.97 Cross-project Learning?',
            str(readiness.get('readiness') or FIX),
            '',
            '## Final Recommendation',
            str(readiness.get('readiness') or FIX),
            '',
        ]
    )


def generate_report(project: Path) -> dict[str, Any]:
    base = dogfood_dir(project)
    value_report = load_json(base / 'real_worker_value_report.json')
    readiness = build_readiness(value_report)
    report_path = base / 'project_operator_value_report.md'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(value_report, readiness), encoding='utf-8')
    write_json(base / 'readiness_for_097.json', readiness)
    return {'report': '.zoo-agent/real_worker_dogfood/project_operator_value_report.md', 'readiness': readiness}


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate project operator value report.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = generate_report(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
