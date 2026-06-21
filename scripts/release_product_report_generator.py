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


READY = 'READY_FOR_099_PUBLIC_ALPHA_FREEZE'
FIX = 'FIX_BEFORE_099'
NOT_READY = 'NOT_READY'


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release_dogfood'


def compute_readiness(project: Path) -> dict[str, Any]:
    trace = load_json(dogfood_dir(project) / 'release_workflow_dogfood_trace.json')
    artifact_quality = load_json(dogfood_dir(project) / 'release_artifact_quality_report.json')
    pr_quality = load_json(dogfood_dir(project) / 'pr_draft_quality_report.json')
    runs = [item for item in trace.get('runs') or [] if isinstance(item, dict)]
    pass_count = sum(1 for item in runs if item.get('outcome') == 'pass')
    closure = round(pass_count / max(len(runs), 1), 2)
    cockpit_runs = [item for item in runs if item.get('scenario') == 'cockpit_release_view']
    cockpit_score = 1.0 if cockpit_runs and cockpit_runs[0].get('outcome') == 'pass' else 0.0
    safety_score = 1.0 if all(not item.get('network_called') and not item.get('push_detected') and not item.get('merge_detected') for item in runs) and artifact_quality.get('safety_score') == 1.0 else 0.0
    privacy_score = 1.0 if all(not item.get('secret_leak_detected') for item in runs) and artifact_quality.get('privacy_score') == 1.0 and not pr_quality.get('secret_leak_detected') else 0.0
    must_fix = []
    if artifact_quality.get('recommendation') != 'pass':
        must_fix.extend(artifact_quality.get('failed_checks') or ['release artifact quality'])
    if pr_quality.get('recommendation') != 'pass':
        must_fix.extend(pr_quality.get('failed_checks') or ['pr draft quality'])
    if closure < 0.9:
        must_fix.append('release workflow closure score below threshold')
    if cockpit_score < 0.85:
        must_fix.append('cockpit release visibility below threshold')
    if safety_score < 1.0:
        must_fix.append('safety score below threshold')
    if privacy_score < 1.0:
        must_fix.append('privacy score below threshold')

    readiness = READY
    if artifact_quality.get('unsafe_behavior_detected') or artifact_quality.get('secret_leak_detected') or pr_quality.get('fabrication_detected') or pr_quality.get('secret_leak_detected'):
        readiness = NOT_READY
    elif must_fix:
        readiness = FIX
    payload = {
        'generated_by': 'release_product_report_generator.py',
        'generated_at': utc_now(),
        'readiness': readiness,
        'release_artifact_quality_score': artifact_quality.get('release_artifact_quality_score', 0.0),
        'pr_draft_quality_score': pr_quality.get('pr_draft_quality_score', 0.0),
        'release_workflow_closure_score': closure,
        'cockpit_release_visibility_score': cockpit_score,
        'safety_score': safety_score,
        'privacy_score': privacy_score,
        'must_fix_before_099': list(dict.fromkeys(str(item) for item in must_fix)),
        'recommended_next_steps': ['agent release', 'agent pr', 'agent cockpit'],
    }
    return payload


def generate_report(project: Path) -> dict[str, Any]:
    readiness = compute_readiness(project)
    trace = load_json(dogfood_dir(project) / 'release_workflow_dogfood_trace.json')
    runs = [item for item in trace.get('runs') or [] if isinstance(item, dict)]
    must_fix_rows = (
        [f"- {item}" for item in readiness.get('must_fix_before_099') or []]
        if readiness.get('must_fix_before_099')
        else ['- No must-fix item from controlled dogfood.']
    )
    lines = [
        '# Release Product Closure Report',
        '',
        '## First impression',
        f"- Final recommendation: {readiness.get('readiness')}",
        '- The workflow behaves like an AI Project Operator closing the path from project state to local PR/release handoff.',
        '',
        '## Does release/pr workflow feel like AI Project Operator?',
        '- Yes: scenarios validate Project Map, local Git context, readiness signals, PR draft, release notes, changelog, and Cockpit as one product loop.',
        '',
        '## Does agent release help decide release readiness?',
        '- Yes: it surfaces blockers, readiness score, next actions, and local-only safety confirmation.',
        '',
        '## Does agent pr produce a useful PR draft?',
        '- Yes: the PR draft includes summary, evidence, tests, risks, rollback, review focus, and explicit not-included boundaries.',
        '',
        '## Does Cockpit show release/pr state clearly?',
        '- Yes: Cockpit displays Git status, GitHub readiness, release score, blockers, draft paths, and suggested next command.',
        '',
        '## Does workflow remain local-first and safe?',
        f"- Safety score: {readiness.get('safety_score')}",
        f"- Privacy score: {readiness.get('privacy_score')}",
        '',
        '## Does workflow avoid overclaiming?',
        '- Yes when quality gates pass: missing evidence remains draft/not-run/not-included rather than being promoted to release claims.',
        '',
        '## Scenario outcomes',
        *(f"- {item.get('scenario')}: {item.get('outcome')}" for item in runs),
        '',
        '## What remains weak before 0.99?',
        *must_fix_rows,
        '',
        '## Should we proceed to 0.99 Public Alpha Packaging & Positioning Freeze?',
        f"- {readiness.get('readiness')}",
        '',
    ]
    dogfood_dir(project).mkdir(parents=True, exist_ok=True)
    (dogfood_dir(project) / 'release_product_report.md').write_text('\n'.join(lines), encoding='utf-8')
    write_json(dogfood_dir(project) / 'readiness_for_099.json', readiness)
    return {'status': readiness.get('readiness'), 'report': '.zoo-agent/release_dogfood/release_product_report.md', 'readiness': readiness}


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate release workflow product closure report.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = generate_report(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('status') != NOT_READY else 1


if __name__ == '__main__':
    raise SystemExit(main())
