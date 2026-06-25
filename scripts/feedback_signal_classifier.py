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
from runtime_common import project_root, utc_now, write_json


def _strength(count: int) -> str:
    if count >= 3:
        return 'strong'
    if count >= 1:
        return 'medium'
    return 'weak'


def classify(project: Path) -> dict[str, Any]:
    write_schema(project)
    items = load_items(project, create_sample=True)
    text_by_item = {
        str(item.get('feedback_id')): f'{item.get("summary", "")} {item.get("raw_feedback_sanitized", "")}'.lower()
        for item in items
    }

    signals: list[dict[str, Any]] = []

    def add(signal_type: str, evidence_ids: list[str], response: str) -> None:
        signals.append(
            {
                'signal_id': f'signal-{signal_type}',
                'type': signal_type,
                'strength': _strength(len(evidence_ids)),
                'evidence': evidence_ids,
                'recommended_response': response,
            }
        )

    codex_confusion = [
        fid
        for fid, text in text_by_item.items()
        if 'codex' in text and ('wrapper' in text or 'why not' in text or 'directly' in text)
    ]
    map_useful = [fid for fid, text in text_by_item.items() if 'project map' in text or 'map' in text]
    cockpit = [fid for fid, text in text_by_item.items() if 'cockpit' in text or 'next step' in text]
    release = [fid for fid, text in text_by_item.items() if 'release' in text or 'pr' in text]
    first_run = [
        fid
        for fid, text in text_by_item.items()
        if 'first' in text or 'install' in text or 'push main' in text or 'release branch' in text
    ]
    safety = [fid for fid, text in text_by_item.items() if 'secret' in text or 'privacy' in text or 'unsafe' in text]

    if codex_confusion:
        add(
            'positioning',
            codex_confusion,
            'Clarify that Codex is a worker and the product is Project Map-backed Autopilot.',
        )
    if map_useful:
        add('map_quality', map_useful, 'Keep Project Map visible in onboarding and Cockpit.')
    if cockpit:
        add('cockpit_clarity', cockpit, 'Improve Cockpit wording around next action and project state.')
    if release:
        add(
            'release_workflow_value', release, 'Preserve local release/PR draft workflow and clarify manual publishing.'
        )
    if first_run:
        add('activation', first_run, 'Patch first-run and branch-aware publishing guidance.')
    if safety:
        add('safety', safety, 'Treat privacy/safety reports as must-fix before feature work.')

    risks = []
    if codex_confusion:
        risks.append('Codex wrapper confusion can weaken positioning.')
    if first_run:
        risks.append('First-run branch/publishing uncertainty can block activation.')
    opportunities = []
    if release:
        opportunities.append('Local release/PR workflow is a differentiated trust-building path.')
    if map_useful or cockpit:
        opportunities.append('Project Map and Cockpit can explain the operator layer.')

    payload = {
        'generated_at': utc_now(),
        'signals': signals,
        'top_product_risks': risks,
        'top_product_opportunities': opportunities,
    }
    write_json(feedback_dir(project) / 'feedback_signal_report.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = classify(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
