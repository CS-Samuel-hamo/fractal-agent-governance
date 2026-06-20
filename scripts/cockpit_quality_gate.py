#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


INTERNAL_TERMS = [
    'eval',
    'governance',
    'planner',
    'verifier',
    'scheduler',
    'backend internals',
    'execution_result',
    'pipeline_loop.py',
    'goal_state_manager',
]
SENSITIVE_TERMS = ['.env', 'api key', 'apikey', 'secret', 'token', 'credential']
CORE_SECTIONS = {
    'project_header': ['ai project operator', '<h1'],
    'project_state': ['current state', 'project_state_badge'],
    'autopilot_session': ['autopilot session'],
    'current_next_action': ['current action', 'next action'],
    'project_map': ['project map'],
    'capabilities': ['capabilities'],
    'risks': ['risks'],
    'attention_required': ['attention required'],
    'safety_recovery': ['safety / recovery'],
    'commands': ['agent status', 'agent continue', 'agent stop', 'agent undo'],
}


def contains_any(text: str, values: list[str]) -> bool:
    lowered = text.lower()
    return any(value in lowered for value in values)


def section_present(html: str, data: dict[str, Any], section: str, needles: list[str]) -> bool:
    lowered = html.lower()
    if section == 'project_state':
        return bool((data.get('project') or {}).get('state')) and ('badge' in lowered)
    return all(needle in lowered for needle in needles)


def external_dependency_detected(html: str) -> bool:
    lowered = html.lower()
    if 'http://' in lowered or 'https://' in lowered or 'cdn.' in lowered:
        return True
    return bool(re.search(r'<script[^>]+src=', lowered) or re.search(r'<link[^>]+href=', lowered))


def raw_json_detected(html: str) -> bool:
    lowered = html.lower()
    return '<pre' in lowered or '"schema_version"' in lowered or '"project":' in lowered or 'cockpit_data.json' in lowered


def score_report(html: str, data: dict[str, Any]) -> dict[str, Any]:
    missing = [name for name, needles in CORE_SECTIONS.items() if not section_present(html, data, name, needles)]
    scan_text = html.lower() + '\n' + json.dumps(data, ensure_ascii=False).lower()
    internal = [term for term in INTERNAL_TERMS if term in scan_text]
    sensitive = [term for term in SENSITIVE_TERMS if term in scan_text]
    external = external_dependency_detected(html)
    raw_json = raw_json_detected(html)
    section_score = (len(CORE_SECTIONS) - len(missing)) / max(len(CORE_SECTIONS), 1)
    product_clarity = 0.35
    if (data.get('project') or {}).get('name'):
        product_clarity += 0.15
    if (data.get('session') or {}).get('next_action'):
        product_clarity += 0.15
    if (data.get('attention') or {}).get('items') is not None:
        product_clarity += 0.1
    if (data.get('safety') or {}).get('checkpoints_available') is not None:
        product_clarity += 0.1
    if len(data.get('map', {}).get('modules') or []) > 0:
        product_clarity += 0.15
    product_clarity = round(min(product_clarity, 1.0), 3)
    operator_score = 0.2
    if 'ai project operator' in html.lower():
        operator_score += 0.2
    if 'project map' in html.lower():
        operator_score += 0.15
    if 'autopilot session' in html.lower():
        operator_score += 0.15
    if 'next actions' in html.lower():
        operator_score += 0.15
    if 'progress timeline' in html.lower():
        operator_score += 0.1
    if 'log' in html.lower() or raw_json:
        operator_score -= 0.2
    operator_score = round(max(0.0, min(operator_score, 1.0)), 3)
    quality = round((section_score * 0.5) + (product_clarity * 0.25) + (operator_score * 0.25), 3)
    ux_blockers = []
    if internal:
        ux_blockers.append('internal_terms_leaked')
    if sensitive:
        ux_blockers.append('sensitive_terms_leaked')
    if raw_json:
        ux_blockers.append('raw_json_visible')
    if missing:
        ux_blockers.append('missing_core_sections')
    if external:
        ux_blockers.append('external_dependency_detected')
    if internal or sensitive:
        recommendation = 'fail'
    elif quality >= 0.85 and not missing and not external and not raw_json:
        recommendation = 'pass'
    elif external or missing or raw_json:
        recommendation = 'fix_before_095'
    else:
        recommendation = 'fix_before_095'
    return {
        'schema_version': '1.0',
        'generated_by': 'cockpit_quality_gate.py',
        'generated_at': utc_now(),
        'cockpit_quality_score': quality,
        'product_clarity_score': product_clarity,
        'operator_positioning_score': operator_score,
        'internal_leakage_detected': bool(internal),
        'external_dependency_detected': external,
        'missing_sections': missing,
        'ux_blockers': ux_blockers,
        'recommendation': recommendation,
    }


def run_quality_gate(project: Path, *, html_path: Path | None = None, data_path: Path | None = None, output: Path | None = None) -> dict[str, Any]:
    html_path = html_path or project / '.zoo-agent' / 'cockpit' / 'index.html'
    data_path = data_path or project / '.zoo-agent' / 'cockpit' / 'cockpit_data.json'
    output = output or project / '.zoo-agent' / 'cockpit_dogfood' / 'cockpit_quality_report.json'
    html = html_path.read_text(encoding='utf-8', errors='replace') if html_path.exists() else ''
    data = load_json(data_path)
    payload = score_report(html, data)
    if not html_path.exists():
        payload['missing_sections'] = sorted(set([*payload['missing_sections'], 'cockpit_html']))
        payload['ux_blockers'] = sorted(set([*payload['ux_blockers'], 'missing_cockpit_html']))
        payload['recommendation'] = 'fix_before_095'
    if not data_path.exists():
        payload['missing_sections'] = sorted(set([*payload['missing_sections'], 'cockpit_data']))
        payload['ux_blockers'] = sorted(set([*payload['ux_blockers'], 'missing_cockpit_data']))
        payload['recommendation'] = 'fix_before_095'
    write_json(output, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate Project Cockpit product quality.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--html', default='')
    parser.add_argument('--data', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = run_quality_gate(
        project,
        html_path=Path(args.html).resolve() if args.html else None,
        data_path=Path(args.data).resolve() if args.data else None,
        output=Path(args.output).resolve() if args.output else None,
    )
    print(json.dumps({'status': 'ok', 'recommendation': payload['recommendation'], 'cockpit_quality_score': payload['cockpit_quality_score']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
