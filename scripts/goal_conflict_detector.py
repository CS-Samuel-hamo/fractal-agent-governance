#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from filter_system_goals import filter_goals
from goal_state_manager import apply_goal_state_patch_data, build_state_patch, load_goal_state, sync_goals
from runtime_common import load_json, project_root, utc_now, write_json

CRITICAL_MARKERS = ['api_contract', 'schema', 'database', 'auth_security', 'public_api', 'dto']


def normalize_resource(resource: str) -> str:
    return str(resource).replace('\\', '/').strip().lower()


def resource_map_resources(project: Path) -> set[str]:
    payload = load_json(project / '.zoo-agent' / 'project-resource-map.json')
    values: set[str] = set()
    for item in payload.get('resources') or []:
        if not isinstance(item, dict):
            continue
        if item.get('resource_id'):
            values.add(normalize_resource(str(item.get('resource_id'))))
        if item.get('name'):
            values.add(normalize_resource(str(item.get('name'))))
        for path in item.get('paths') or []:
            values.add(normalize_resource(str(path)))
    return values


def severity_for(shared: set[str]) -> str:
    surface = ' '.join(sorted(shared))
    if any(marker in surface for marker in CRITICAL_MARKERS):
        return 'critical'
    if any(item.endswith(('.py', '.ts', '.tsx', '.js', '.jsx', '.sql')) for item in shared):
        return 'high'
    if any(item.endswith('.md') or item.startswith('docs/') for item in shared):
        return 'medium'
    return 'medium'


def conflict_type_for(shared: set[str]) -> str:
    surface = ' '.join(sorted(shared))
    if 'schema' in surface or 'database' in surface:
        return 'schema'
    if 'api' in surface or 'contract' in surface:
        return 'api'
    if 'depends' in surface:
        return 'dependency'
    return 'resource'


def resolution_for(severity: str) -> str:
    if severity == 'critical':
        return 'pause'
    if severity == 'high':
        return 'reorder'
    if severity == 'medium':
        return 'defer'
    return 'defer'


def detect_conflicts(project: Path) -> dict[str, Any]:
    state = sync_goals(project)
    production_goal_ids = {str(item.get('goal_id')) for item in filter_goals(state).get('eligible_goals') or []}
    goals = [
        dict(item)
        for item in state.get('goals') or []
        if item.get('status') not in {'completed', 'blocked'} and item.get('goal_id') in production_goal_ids
    ]
    resource_map_known = resource_map_resources(project)
    conflicts: list[dict[str, Any]] = []
    for left_index, left in enumerate(goals):
        left_resources = {normalize_resource(item) for item in left.get('resource_usage') or [] if str(item).strip()}
        if not left_resources and resource_map_known:
            left_resources = set()
        for right in goals[left_index + 1 :]:
            right_resources = {
                normalize_resource(item) for item in right.get('resource_usage') or [] if str(item).strip()
            }
            shared = left_resources & right_resources
            if not shared:
                continue
            severity = severity_for(shared)
            conflicts.append(
                {
                    'goal_a': left.get('goal_id'),
                    'goal_b': right.get('goal_id'),
                    'type': conflict_type_for(shared),
                    'severity': severity,
                    'shared_resources': sorted(shared),
                    'resolution': resolution_for(severity),
                }
            )
    return {
        'schema_version': '1.0',
        'generated_by': 'goal_conflict_detector.py',
        'generated_at': utc_now(),
        'conflicts': conflicts,
        'resource_map_used': bool(resource_map_known),
        'resource_map_resource_count': len(resource_map_known),
    }


def apply_conflict_resolutions(project: Path, report: dict[str, Any]) -> dict[str, Any]:
    state = load_goal_state(project)
    goals_by_id = {str(item.get('goal_id')): item for item in state.get('goals') or []}
    changes: list[dict[str, Any]] = []
    paused: list[str] = []
    for conflict in report.get('conflicts') or []:
        if conflict.get('severity') not in {'critical', 'high'}:
            continue
        left = goals_by_id.get(str(conflict.get('goal_a')))
        right = goals_by_id.get(str(conflict.get('goal_b')))
        if not left or not right:
            continue
        left_priority = int(left.get('priority') or 0)
        right_priority = int(right.get('priority') or 0)
        loser = right if left_priority >= right_priority else left
        loser_id = str(loser.get('goal_id') or '')
        loser_status = str(loser.get('status') or 'paused')
        if loser_status in {'completed', 'blocked', 'backlog'}:
            continue
        reason = (
            f'conflict_{conflict.get("resolution") or "pause"}:'
            f'{conflict.get("goal_a")}:{conflict.get("goal_b")}:'
            f'{",".join(str(item) for item in conflict.get("shared_resources") or [])}'
        )
        if loser_status == 'active':
            changes.append(
                {
                    'goal_id': loser_id,
                    'op': 'set_status',
                    'from': 'active',
                    'to': 'paused',
                    'requires_explicit_reason': True,
                    'reason': reason,
                }
            )
        else:
            changes.append(
                {
                    'goal_id': loser_id,
                    'op': 'append_event',
                    'reason': reason,
                    'payload': {'conflict': conflict},
                }
            )
        paused.append(loser_id)
    if changes:
        patch = build_state_patch(
            project, source='conflict_detector', reason='cross_goal_conflict_resolution', changes=changes
        )
        patch_path = project / '.zoo-agent' / 'goal' / 'goal-conflict-state-patch.json'
        write_json(patch_path, patch)
        result = apply_goal_state_patch_data(project, patch)
        report['state_patch'] = str(patch_path)
        report['state_diff'] = result.get('paths', {}).get('goal_state_diff', '')
    report['applied'] = True
    report['paused_goals'] = sorted(set(paused))
    return report


def write_conflict_report(project: Path, report: dict[str, Any]) -> dict[str, str]:
    path = project / '.zoo-agent' / 'goal' / 'goal-conflicts.json'
    write_json(path, report)
    return {'goal_conflicts': str(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description='Detect cross-goal resource and semantic conflicts.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = detect_conflicts(project)
    if args.apply:
        report = apply_conflict_resolutions(project, report)
    paths = write_conflict_report(project, report)
    print(
        json.dumps({'status': 'ok', 'workspace': str(project), 'paths': paths, **report}, ensure_ascii=False, indent=2)
    )
    return 0 if not any(item.get('severity') == 'critical' for item in report.get('conflicts') or []) else 10


if __name__ == '__main__':
    raise SystemExit(main())
