#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_map_builder import build_project_map
from project_map_schema import map_dir
from runtime_common import load_json, project_root, utc_now, write_json
from trust_zone_classifier import classify_trust_zone


def action_history(project: Path) -> list[dict[str, Any]]:
    payload = load_json(project / '.zoo-agent' / 'autopilot' / 'action_history.json')
    return [item for item in payload.get('actions') or [] if isinstance(item, dict)]


def _score(action: dict[str, Any], seen: set[str], seen_files: set[str]) -> float:
    score = 0.0
    if action.get('autopilot_eligible'):
        score += 2.0
    if action.get('risk_level') == 'low':
        score += 2.0
    if action.get('target_files'):
        score += 1.0
    if action.get('evidence'):
        score += 1.0
    if str(action.get('action_id')) in seen:
        score -= 4.0
    targets = {str(item).replace('\\', '/') for item in action.get('target_files') or []}
    if targets & seen_files:
        score -= 3.0
    title = str(action.get('title') or '').lower()
    if any(word in title for word in ['readme', 'docs', 'test']):
        score += 0.5
    return score


def action_is_autopilot_ready(action: dict[str, Any]) -> bool:
    return bool(
        action.get('autopilot_eligible')
        and action.get('why_now')
        and action.get('target_files')
        and action.get('expected_impact')
        and action.get('evidence')
    )


def select_next_action(project: Path, *, mode: str = 'standard') -> dict[str, Any]:
    map_path = map_dir(project) / 'project_map.json'
    project_map = load_json(map_path)
    if not project_map:
        project_map, state, evidence = build_project_map(project)
        write_json(map_dir(project) / 'project_map.json', project_map)
        write_json(map_dir(project) / 'project_state.json', state)
        write_json(map_dir(project) / 'map_evidence.json', evidence)

    actions = [item for item in project_map.get('next_actions') or [] if isinstance(item, dict)]
    ready_actions = [item for item in actions if action_is_autopilot_ready(item)]
    history = action_history(project)
    seen = {str(item.get('action_id') or item.get('selected_action_id') or '') for item in history}
    seen_files = {str(path).replace('\\', '/') for item in history for path in (item.get('target_files') or [])}
    if not ready_actions:
        payload = {
            'schema_version': '1.0',
            'generated_by': 'map_task_selector.py',
            'generated_at': utc_now(),
            'selected_action_id': '',
            'reason': 'no_executable_map_backed_next_action_available',
            'expected_project_progress': 'none',
            'risk_level': 'unknown',
            'target_files': [],
            'execution_mode': 'needs_attention',
            'trust_zone': 'blocked',
        }
        write_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json', payload)
        return payload

    selected = sorted(ready_actions, key=lambda item: _score(item, seen, seen_files), reverse=True)[0]
    trust = classify_trust_zone(title=str(selected.get('title') or ''), target_files=[str(item) for item in selected.get('target_files') or []], risk_level=str(selected.get('risk_level') or 'unknown'))
    if mode == 'preview':
        execution_mode = 'preview'
    elif mode == 'autopilot':
        execution_mode = trust.get('autopilot_mode')
    else:
        execution_mode = trust.get('standard_mode')
    payload = {
        'schema_version': '1.0',
        'generated_by': 'map_task_selector.py',
        'generated_at': utc_now(),
        'selected_action_id': selected.get('action_id', ''),
        'title': selected.get('title', ''),
        'reason': selected.get('why_now', ''),
        'expected_project_progress': selected.get('expected_impact', ''),
        'risk_level': selected.get('risk_level', 'unknown'),
        'target_files': selected.get('target_files') or [],
        'execution_mode': execution_mode,
        'trust_zone': trust.get('zone'),
        'trust_zone_reasons': trust.get('reasons') or [],
        'source': 'project_map.next_actions',
        'project_map_ref': str(map_path),
    }
    write_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Select the next project-map-backed action.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='standard')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = select_next_action(project, mode=args.mode)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
