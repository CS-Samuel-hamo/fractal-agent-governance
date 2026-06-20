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


def final_recommendation(quality: dict[str, Any]) -> str:
    if quality.get('recommendation') == 'pass':
        return 'READY_FOR_095_SESSION_RUNTIME'
    if quality.get('recommendation') == 'fix_before_095':
        return 'FIX_BEFORE_095'
    return 'NOT_READY'


def status_line(condition: bool, yes: str, no: str) -> str:
    return yes if condition else no


def generate_report(
    project: Path,
    *,
    output: Path | None = None,
    quality_path: Path | None = None,
    demo_path: Path | None = None,
    data_path: Path | None = None,
) -> dict[str, Any]:
    dogfood_dir = project / '.zoo-agent' / 'cockpit_dogfood'
    quality = load_json(quality_path or dogfood_dir / 'cockpit_quality_report.json')
    demo = load_json(demo_path or dogfood_dir / 'demo_fixture_summary.json')
    data = load_json(data_path or project / '.zoo-agent' / 'cockpit' / 'cockpit_data.json')
    recommendation = final_recommendation(quality)
    project_info = data.get('project') or {}
    session = data.get('session') or {}
    project_map = data.get('map') or {}
    attention = data.get('attention') or {}
    safety = data.get('safety') or {}
    blockers = quality.get('ux_blockers') or []
    missing = quality.get('missing_sections') or []
    must_fix = []
    if quality.get('internal_leakage_detected'):
        must_fix.append('Remove internal terminology from the Cockpit surface.')
    if quality.get('external_dependency_detected'):
        must_fix.append('Remove external dependencies so the Cockpit remains offline.')
    if missing:
        must_fix.append('Restore missing Cockpit sections: ' + ', '.join(str(item) for item in missing))
    if not must_fix and recommendation == 'READY_FOR_095_SESSION_RUNTIME':
        must_fix.append('No blocking fixes required before 0.95.')
    lines = [
        '# Project Cockpit Dogfood UX Report',
        '',
        f'Generated: {utc_now()}',
        '',
        '## First Impression',
        '',
        f'- Project: {project_info.get("name") or "not available"}',
        f'- State: {project_info.get("state") or "unknown"}',
        f'- Quality score: {quality.get("cockpit_quality_score")}',
        f'- Recommendation: {recommendation}',
        '',
        '## Can User Understand Project State?',
        '',
        '- ' + status_line(bool(project_info.get('name') and project_info.get('state')), 'Yes. The header exposes project name, goal, state, and updated time.', 'Not fully. Project identity or state is missing.'),
        '',
        '## Can User Understand AI Progress?',
        '',
        '- ' + status_line(bool((data.get('progress') or {}).get('completed_actions') or (data.get('progress') or {}).get('recent_changes')), 'Yes. Progress timeline and recent changes are visible.', 'Partially. No completed actions or recent changes are visible yet.'),
        '',
        '## Can User Understand Next Action?',
        '',
        '- ' + status_line(bool(session.get('next_action') or project_map.get('next_actions')), 'Yes. The next action and action cards are visible.', 'No. No next action is visible.'),
        '',
        '## Can User See Attention Required?',
        '',
        '- ' + status_line(bool(attention.get('requires_attention') or attention.get('items') is not None), 'Yes. Attention state has a dedicated section.', 'No. Attention state is not represented.'),
        '',
        '## Can User Recover / Undo?',
        '',
        '- ' + status_line(bool(safety.get('checkpoints_available') or safety.get('undo_available')), 'Yes. Checkpoint and undo availability are visible.', 'Partially. No checkpoint is available in the current artifacts.'),
        '',
        '## Does This Feel Like AI Project Operator?',
        '',
        f'- Operator positioning score: {quality.get("operator_positioning_score")}',
        '- ' + status_line(float(quality.get('operator_positioning_score') or 0) >= 0.85, 'Yes. The Cockpit emphasizes project state, map, next actions, progress, attention, and recovery.', 'Not yet. It still needs stronger project-operation framing.'),
        '',
        '## What Is Still Too Technical?',
        '',
        '- ' + (', '.join(str(item) for item in blockers) if blockers else 'No blocking technical leakage detected.'),
        '',
        '## What Must Be Fixed Before 0.95?',
        '',
    ]
    lines.extend(f'- {item}' for item in must_fix)
    lines.extend(
        [
            '',
            '## Demo Fixture',
            '',
            f'- Fixture path: {demo.get("fixture_path") or "not available"}',
            f'- Scenarios: {", ".join(str(item) for item in demo.get("scenarios") or [])}',
            f'- Safe to use: {demo.get("safe_to_use")}',
            '',
            '## Final Recommendation',
            '',
            recommendation,
            '',
        ]
    )
    output = output or dogfood_dir / 'cockpit_ux_report.md'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines), encoding='utf-8')
    return {
        'status': 'ok',
        'report': str(output),
        'recommendation': recommendation,
        'must_fix_before_095': must_fix,
        'recommended_next_steps': ['Enter 0.95 Session Runtime design.' if recommendation == 'READY_FOR_095_SESSION_RUNTIME' else 'Fix Cockpit UX blockers before 0.95.'],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a Project Cockpit dogfood UX report.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--output', default='')
    parser.add_argument('--quality-report', default='')
    parser.add_argument('--demo-summary', default='')
    parser.add_argument('--cockpit-data', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = generate_report(
        project,
        output=Path(args.output).resolve() if args.output else None,
        quality_path=Path(args.quality_report).resolve() if args.quality_report else None,
        demo_path=Path(args.demo_summary).resolve() if args.demo_summary else None,
        data_path=Path(args.cockpit_data).resolve() if args.cockpit_data else None,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
