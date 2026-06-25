#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


def readiness_verdict(map_quality: dict[str, Any], trace: dict[str, Any]) -> str:
    runs = [item for item in trace.get('runs') or [] if isinstance(item, dict)]
    if not runs or map_quality.get('recommendation') == 'fail':
        return 'NOT_READY_FOR_PRODUCT_UI'
    structural_ok = all(
        run.get('source') == 'project_map.next_actions'
        and run.get('checkpoint_created')
        and run.get('map_updated')
        and run.get('progress_summary_created')
        for run in runs
    )
    bad_outcomes = [run for run in runs if run.get('outcome') in {'failed', 'blocked'}]
    if map_quality.get('recommendation') == 'pass' and structural_ok and not bad_outcomes:
        return 'READY_FOR_094_COCKPIT'
    return 'FIX_BEFORE_094'


def render_report(map_quality: dict[str, Any], trace: dict[str, Any], readiness: dict[str, Any]) -> str:
    runs = [item for item in trace.get('runs') or [] if isinstance(item, dict)]
    delivered = sum(1 for item in runs if item.get('outcome') == 'delivered')
    no_delivery = sum(1 for item in runs if item.get('outcome') == 'no_delivery')
    blocked = sum(1 for item in runs if item.get('outcome') == 'blocked')
    failed = sum(1 for item in runs if item.get('outcome') == 'failed')
    checkpoint_ok = sum(1 for item in runs if item.get('checkpoint_created'))
    map_ok = sum(1 for item in runs if item.get('map_updated'))
    progress_ok = sum(1 for item in runs if item.get('progress_summary_created'))
    lines = [
        '# Dogfood Report',
        '',
        '## Project Map Accuracy',
        f'- score: {map_quality.get("map_quality_score")}',
        f'- recommendation: {map_quality.get("recommendation")}',
        f'- hallucination_risk: {map_quality.get("hallucination_risk")}',
        '',
        '## Evidence Coverage',
        f'- evidence_coverage: {map_quality.get("evidence_coverage")}',
        f'- unsupported_module_count: {map_quality.get("unsupported_module_count")}',
        f'- unsupported_capability_count: {map_quality.get("unsupported_capability_count")}',
        '',
        '## Autopilot Usefulness',
        f'- run_count: {len(runs)}',
        f'- delivered: {delivered}',
        f'- no_delivery: {no_delivery}',
        f'- blocked: {blocked}',
        f'- failed: {failed}',
        '',
        '## Next Action Quality',
        f'- vague_action_count: {map_quality.get("vague_action_count")}',
        f'- unsupported_action_count: {map_quality.get("unsupported_action_count")}',
        '',
        '## Progress Summary Quality',
        f'- progress_summary_created: {progress_ok}/{len(runs)}',
        '',
        '## Undo/Checkpoint Reliability',
        f'- checkpoint_created: {checkpoint_ok}/{len(runs)}',
        '- undo_command_available: yes',
        '',
        '## Blocked-zone Behavior',
        f'- attention_required_count: {sum(1 for item in runs if item.get("attention_required"))}',
        '',
        '## Top Failure Modes',
        f'- map_quality: {map_quality.get("recommendation")}',
        f'- no_delivery_count: {no_delivery}',
        f'- failed_count: {failed}',
        '',
        '## Fixes Required Before 0.94',
    ]
    fixes: list[str] = []
    if map_quality.get('recommendation') != 'pass':
        fixes.append('Improve map evidence coverage and next_action specificity.')
    if no_delivery or failed or blocked:
        fixes.append('Improve selected action executability or worker delivery before cockpit UI.')
    if checkpoint_ok != len(runs) or map_ok != len(runs) or progress_ok != len(runs):
        fixes.append('Fix dogfood trace completeness.')
    if not fixes:
        fixes.append('No blocking fixes identified.')
    lines.extend(f'- {item}' for item in fixes)
    lines += ['', '## Final Recommendation', f'- {readiness.get("final_recommendation")}', '']
    return '\n'.join(lines)


def generate_report(project: Path) -> tuple[dict[str, Any], str]:
    dogfood_dir = project / '.zoo-agent' / 'dogfood'
    map_quality = load_json(dogfood_dir / 'map_quality_report.json')
    trace = load_json(dogfood_dir / 'autopilot_trace.json')
    final = readiness_verdict(map_quality, trace)
    readiness = {
        'schema_version': '1.0',
        'generated_by': 'dogfood_report_generator.py',
        'generated_at': utc_now(),
        'final_recommendation': final,
        'map_quality_recommendation': map_quality.get('recommendation', ''),
        'run_count': len(trace.get('runs') or []),
    }
    text = render_report(map_quality, trace, readiness)
    return readiness, text


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate Project Operator dogfood report.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    dogfood_dir = project / '.zoo-agent' / 'dogfood'
    readiness, report = generate_report(project)
    write_json(dogfood_dir / 'readiness_for_094.json', readiness)
    (dogfood_dir / 'dogfood_report.md').write_text(report, encoding='utf-8')
    print(
        json.dumps(
            {
                'status': 'ok',
                'dogfood_report': str(dogfood_dir / 'dogfood_report.md'),
                'final_recommendation': readiness['final_recommendation'],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
