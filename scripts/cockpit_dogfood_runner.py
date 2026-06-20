#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cockpit_demo_fixture_builder import build_demo_fixture  # noqa: E402
from cockpit_quality_gate import run_quality_gate  # noqa: E402
from cockpit_renderer import render_cockpit  # noqa: E402
from cockpit_ux_report_generator import generate_report  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


def readiness_from_quality(quality: dict[str, Any], report_payload: dict[str, Any]) -> dict[str, Any]:
    if quality.get('recommendation') == 'pass':
        readiness = 'READY_FOR_095_SESSION_RUNTIME'
    elif quality.get('recommendation') == 'fix_before_095':
        readiness = 'FIX_BEFORE_095'
    else:
        readiness = 'NOT_READY'
    must_fix = []
    if quality.get('ux_blockers'):
        must_fix.extend(str(item) for item in quality.get('ux_blockers') or [])
    if quality.get('missing_sections'):
        must_fix.append('missing_sections: ' + ', '.join(str(item) for item in quality.get('missing_sections') or []))
    if not must_fix and readiness == 'READY_FOR_095_SESSION_RUNTIME':
        must_fix.append('none')
    return {
        'schema_version': '1.0',
        'generated_by': 'cockpit_dogfood_runner.py',
        'generated_at': utc_now(),
        'readiness': readiness,
        'cockpit_quality_score': quality.get('cockpit_quality_score', 0.0),
        'product_clarity_score': quality.get('product_clarity_score', 0.0),
        'operator_positioning_score': quality.get('operator_positioning_score', 0.0),
        'must_fix_before_095': must_fix,
        'recommended_next_steps': report_payload.get('recommended_next_steps') or [],
    }


def run_dogfood(project: Path) -> dict[str, Any]:
    dogfood_dir = project / '.zoo-agent' / 'cockpit_dogfood'
    dogfood_dir.mkdir(parents=True, exist_ok=True)
    summary = build_demo_fixture(project)
    fixture = project / summary['fixture_path']
    render_payload = render_cockpit(fixture)
    quality_path = dogfood_dir / 'cockpit_quality_report.json'
    quality = run_quality_gate(
        fixture,
        html_path=Path(render_payload['cockpit']),
        data_path=Path(render_payload['cockpit_data']),
        output=quality_path,
    )
    report_payload = generate_report(
        project,
        output=dogfood_dir / 'cockpit_ux_report.md',
        quality_path=quality_path,
        demo_path=dogfood_dir / 'demo_fixture_summary.json',
        data_path=Path(render_payload['cockpit_data']),
    )
    readiness = readiness_from_quality(quality, report_payload)
    readiness_path = dogfood_dir / 'readiness_for_095.json'
    write_json(readiness_path, readiness)
    return {
        'status': 'ok',
        'fixture_summary': str(dogfood_dir / 'demo_fixture_summary.json'),
        'cockpit_html': render_payload['cockpit'],
        'cockpit_data': render_payload['cockpit_data'],
        'quality_report': str(quality_path),
        'ux_report': str(dogfood_dir / 'cockpit_ux_report.md'),
        'readiness': str(readiness_path),
        'readiness_value': readiness['readiness'],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Run Project Cockpit dogfood in a synthetic safe fixture.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = run_dogfood(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
