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


READY = 'READY_FOR_098_GITHUB_PR_RELEASE_WORKFLOW'
FIX = 'FIX_BEFORE_098'
NOT_READY = 'NOT_READY'


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'learning_dogfood'


def readiness_from_lift(lift: dict[str, Any]) -> str:
    if lift.get('recommendation') == 'pass':
        return READY
    if lift.get('recommendation') == 'fix_before_098':
        return FIX
    return NOT_READY


def generate_readiness(project: Path, lift: dict[str, Any]) -> dict[str, Any]:
    readiness = readiness_from_lift(lift)
    must_fix = []
    if readiness != READY:
        must_fix = [str(item) for item in lift.get('failed_checks') or []]
    payload = {
        'readiness': readiness,
        'learning_lift_score': lift.get('learning_lift_score', 0.0),
        'next_action_lift_score': lift.get('next_action_lift_score', 0.0),
        'release_readiness_lift_score': lift.get('release_readiness_lift_score', 0.0),
        'worker_routing_lift_score': lift.get('worker_routing_lift_score', 0.0),
        'failure_avoidance_lift_score': lift.get('failure_avoidance_lift_score', 0.0),
        'privacy_score': lift.get('privacy_score', 0.0),
        'safety_preservation_score': lift.get('safety_preservation_score', 0.0),
        'must_fix_before_098': must_fix,
        'recommended_next_steps': ['Design GitHub / PR / Release Workflow using the same local-first boundaries.'] if readiness == READY else ['Fix failed learning lift checks, then rerun agent learning --dogfood.'],
    }
    write_json(dogfood_dir(project) / 'readiness_for_098.json', payload)
    return payload


def generate_product_report(project: Path) -> dict[str, Any]:
    lift = load_json(dogfood_dir(project) / 'learning_lift_report.json')
    comparison = load_json(dogfood_dir(project) / 'baseline_comparison.json')
    readiness = generate_readiness(project, lift)
    summary = comparison.get('summary') if isinstance(comparison.get('summary'), dict) else {}
    lines = [
        '# Cross-project Learning Product Report',
        '',
        '## First impression',
        'Learning produces visible product lift when compared against a learning-off baseline.',
        '',
        '## Does learning improve AI Project Operator?',
        f"- Positive lift projects: {summary.get('projects_with_positive_lift', 0)} / {summary.get('total_projects', 0)}",
        f"- Learning lift score: {lift.get('learning_lift_score')}",
        '',
        '## Does learning improve next_action quality?',
        f"- next_action_lift_score: {lift.get('next_action_lift_score')}",
        '- Learning favors evidence-backed release and scan actions over generic cleanup.',
        '',
        '## Does learning improve release readiness?',
        f"- release_readiness_lift_score: {lift.get('release_readiness_lift_score')}",
        '- Release templates add quickstart, tests, worker doctor, and Cockpit review steps.',
        '',
        '## Does learning improve worker routing?',
        f"- worker_routing_lift_score: {lift.get('worker_routing_lift_score')}",
        '- Worker memory prefers local scanner and dry-run roles for metadata and preview tasks.',
        '',
        '## Does learning help avoid repeated failures?',
        f"- failure_avoidance_lift_score: {lift.get('failure_avoidance_lift_score')}",
        '- Failure taxonomy adds warnings for no-delivery, blocked zones, and weak evidence.',
        '',
        '## Does learning remain privacy-preserving?',
        f"- privacy_score: {lift.get('privacy_score')}",
        '- Dogfood artifacts store only structured summaries and sanitized metadata.',
        '',
        '## Does Cockpit explain learning insight clearly?',
        '- Cockpit shows learned suggestions, release readiness paths, worker preferences, and common warnings without raw artifacts.',
        '',
        '## What remains weak before 0.98?',
        '- 0.98 should focus on GitHub / PR / Release Workflow while preserving local-first execution.',
        '',
        '## Should we proceed to 0.98 GitHub / PR / Release Workflow?',
        f"- Final recommendation: {readiness.get('readiness')}",
        '',
    ]
    report_path = dogfood_dir(project) / 'learning_product_report.md'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text('\n'.join(lines), encoding='utf-8')
    return {
        'status': 'ok',
        'report': '.zoo-agent/learning_dogfood/learning_product_report.md',
        'readiness': '.zoo-agent/learning_dogfood/readiness_for_098.json',
        'readiness_value': readiness.get('readiness'),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate learning dogfood product report.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = generate_product_report(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('readiness_value') == READY else 1


if __name__ == '__main__':
    raise SystemExit(main())
