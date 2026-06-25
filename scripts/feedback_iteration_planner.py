#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from feedback_intake_schema import feedback_dir, load_items, write_schema
from feedback_priority_ranker import rank
from feedback_signal_classifier import classify
from feedback_triage_engine import triage
from positioning_feedback_analyzer import analyze
from runtime_common import project_root, utc_now, write_json


def write_markdown_plans(project: Path, priority: dict[str, Any], positioning: dict[str, Any]) -> None:
    patch_items = priority.get('top_patch_items') or []
    roadmap_items = priority.get('top_roadmap_items') or []
    patch = [
        '# v1.0.4 Patch Plan',
        '',
        'Scope: safe public alpha patch only. No major product feature expansion.',
        '',
        '## Patch Candidates From Feedback',
        '',
    ]
    patch.extend(f'- `{item}`' for item in patch_items)
    if positioning.get('positioning_risk') != 'low':
        patch.append('- Clarify AI Project Operator positioning in README, FAQ, and community copy.')
    patch.extend(
        [
            '',
            '## Allowed Work',
            '',
            '- docs clarity',
            '- first-run friction',
            '- branch publishing docs',
            '- feedback template improvements',
            '- cockpit wording',
            '- release/pr wording',
            '- safe bug fixes',
            '',
            '## Not Included',
            '',
            '- cloud sync',
            '- plugin marketplace',
            '- enterprise governance system',
        ]
    )
    (project / 'V1_0_4_PATCH_PLAN.md').write_text('\n'.join(patch) + '\n', encoding='utf-8')

    roadmap = [
        '# v1.1 Roadmap Candidates',
        '',
        'These candidates come from feedback signals and remain advisory.',
        '',
        '## Feedback-backed Candidates',
        '',
    ]
    roadmap.extend(f'- `{item}`' for item in roadmap_items)
    roadmap.extend(
        [
            '- stronger Cockpit',
            '- better session autonomy',
            '- optional GitHub integration',
            '- real worker adapter hardening',
            '- packaging / installer',
            '- VS Code extension later',
            '',
            '## Not Commitments',
            '',
            '- cloud sync by default',
            '- plugin marketplace',
        ]
    )
    (project / 'V1_1_ROADMAP_CANDIDATES.md').write_text('\n'.join(roadmap) + '\n', encoding='utf-8')

    summary = [
        '# Alpha Feedback Summary',
        '',
        f'Generated: {utc_now()}',
        '',
        f'- Patch candidates: {len(patch_items)}',
        f'- Roadmap candidates: {len(roadmap_items)}',
        f'- Positioning risk: {positioning.get("positioning_risk")}',
        '',
        '## Current Decision',
        '',
        'Use first feedback to patch activation, positioning, Cockpit wording, and branch-aware publishing before adding large features.',
    ]
    (project / 'ALPHA_FEEDBACK_SUMMARY.md').write_text('\n'.join(summary) + '\n', encoding='utf-8')


def plan(project: Path) -> dict[str, Any]:
    write_schema(project)
    items = load_items(project, create_sample=True)
    triage_report = triage(project)
    signal_report = classify(project)
    priority = rank(project)
    positioning = analyze(project)
    write_markdown_plans(project, priority, positioning)
    payload = {
        'generated_at': utc_now(),
        'feedback_count': len(items),
        'patch_candidates': priority.get('top_patch_items') or [],
        'roadmap_candidates': priority.get('top_roadmap_items') or [],
        'positioning_risk': positioning.get('positioning_risk'),
        'triage_recommendation': triage_report.get('recommendation'),
        'signal_count': len(signal_report.get('signals') or []),
        'written_docs': ['V1_0_4_PATCH_PLAN.md', 'V1_1_ROADMAP_CANDIDATES.md', 'ALPHA_FEEDBACK_SUMMARY.md'],
    }
    write_json(feedback_dir(project) / 'product_iteration_report.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = plan(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
