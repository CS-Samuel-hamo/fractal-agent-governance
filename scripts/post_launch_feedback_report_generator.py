#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from feedback_intake_schema import feedback_dir, write_schema
from feedback_iteration_planner import plan
from feedback_priority_ranker import rank
from feedback_signal_classifier import classify
from feedback_triage_engine import triage
from positioning_feedback_analyzer import analyze
from public_branch_sync_preflight import preflight
from runtime_common import project_root, utc_now, write_json


def readiness(
    sync: dict[str, Any], triage_report: dict[str, Any], positioning: dict[str, Any], iteration: dict[str, Any]
) -> str:
    if not triage_report.get('triage_summary') or positioning.get('positioning_risk') == 'high':
        return 'FIX_FEEDBACK_PIPELINE'
    if iteration.get('patch_candidates'):
        return 'READY_FOR_104_PATCH_PLANNING'
    return 'COLLECT_MORE_FEEDBACK_FIRST'


def generate(project: Path) -> dict[str, Any]:
    schema = write_schema(project)
    sync = preflight(project)
    triage_report = triage(project)
    signals = classify(project)
    priority = rank(project)
    positioning = analyze(project)
    iteration = plan(project)
    status = readiness(sync, triage_report, positioning, iteration)
    manual_actions = []
    if sync.get('manual_sync_recommended'):
        manual_actions.append(
            'Manually sync the public release branch with branch-aware no-force commands if maintainers want latest local docs public.'
        )
    if status == 'COLLECT_MORE_FEEDBACK_FIRST':
        manual_actions.append('Collect first real user feedback before patch planning.')

    report = '\n'.join(
        [
            '# Post-launch Feedback Report',
            '',
            f'Generated: {utc_now()}',
            '',
            '## Recommendation',
            '',
            status,
            '',
            '## Public Branch Sync Status',
            '',
            f'- public branch: `{sync.get("public_branch")}`',
            f'- remote branch exists: {sync.get("remote_branch_exists")}',
            f'- remote contains post-launch docs: {sync.get("remote_contains_postlaunch_docs")}',
            f'- local/remote diff empty: {sync.get("local_remote_diff_empty")}',
            f'- manual sync recommended: {sync.get("manual_sync_recommended")}',
            '',
            '## Feedback Intake Readiness',
            '',
            f'- schema path: `{schema.get("path")}`',
            f'- total feedback items: {triage_report.get("triage_summary", {}).get("total")}',
            '',
            '## Positioning Clarity',
            '',
            f'- positioning risk: {positioning.get("positioning_risk")}',
            f'- Codex wrapper confusion rate: {positioning.get("codex_wrapper_confusion_rate")}',
            '',
            '## Product Signals',
            '',
        ]
    )
    for signal in signals.get('signals') or []:
        report += f'- {signal.get("type")}: {signal.get("strength")} ({signal.get("recommended_response")})\n'
    report += '\n## Top Patch Candidates\n\n'
    for item in priority.get('top_patch_items') or []:
        report += f'- `{item}`\n'
    report += '\n## Top Roadmap Candidates\n\n'
    for item in priority.get('top_roadmap_items') or []:
        report += f'- `{item}`\n'
    report += '\n## Product Risks\n\n'
    for risk in signals.get('top_product_risks') or [
        'No critical product risk detected in current sanitized sample set.'
    ]:
        report += f'- {risk}\n'
    report += '\n## Manual Remaining Actions\n\n'
    for action in manual_actions or ['Collect real first-user feedback and continue weekly triage.']:
        report += f'- {action}\n'

    out = feedback_dir(project)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'post_launch_feedback_report.md').write_text(report, encoding='utf-8')
    sync_status = (
        'synced'
        if sync.get('local_remote_diff_empty')
        else 'local_ahead'
        if sync.get('manual_sync_recommended')
        else 'inconclusive'
    )
    readiness_payload = {
        'generated_at': utc_now(),
        'readiness': status,
        'feedback_pipeline_ready': True,
        'public_branch_sync_status': sync_status,
        'positioning_risk': positioning.get('positioning_risk'),
        'first_user_flow_risk': 'medium' if triage_report.get('patch_candidates') else 'low',
        'must_fix_now': triage_report.get('must_fix_now') or [],
        'patch_candidates': priority.get('top_patch_items') or [],
        'roadmap_candidates': priority.get('top_roadmap_items') or [],
        'manual_actions': manual_actions,
    }
    write_json(out / 'readiness_for_104_patch.json', readiness_payload)
    payload = {
        'status': status,
        'report_path': '.zoo-agent/feedback/post_launch_feedback_report.md',
        'readiness_path': '.zoo-agent/feedback/readiness_for_104_patch.json',
        'readiness': readiness_payload,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = generate(project_root(args.workspace))
    return 0 if payload.get('status') in {'READY_FOR_104_PATCH_PLANNING', 'COLLECT_MORE_FEEDBACK_FIRST'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
