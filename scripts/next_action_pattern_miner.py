#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cross_project_store import store_dir, write_store
from runtime_common import load_json, project_root

DEFAULT_PATTERNS = {
    'docs_cleanup_before_release': ('docs_update', 'Documentation cleanup reduces release friction.'),
    'quickstart_before_public_release': ('docs_update', 'Quickstart clarity helps first-run success.'),
    'tests_before_refactor': ('test_update', 'Tests reduce regression risk before refactor work.'),
    'local_scan_before_autopilot': ('repo_scan', 'Local scan provides evidence before selecting project actions.'),
    'cockpit_before_long_session': (
        'release_readiness',
        'Cockpit improves project state readability before long sessions.',
    ),
    'worker_doctor_before_real_execution': (
        'analysis',
        'Worker doctor explains local capabilities before real execution.',
    ),
    'stop_on_no_delivery': ('failure_warning', 'Repeated no-delivery should pause instead of retrying blindly.'),
    'blocked_zone_requires_attention': (
        'failure_warning',
        'Blocked zones require user attention, not worker fallback.',
    ),
}


def imported_bundles(project: Path) -> list[dict[str, Any]]:
    rows = []
    base = store_dir(project) / 'imported_projects'
    for path in sorted(base.glob('*.json')):
        payload = load_json(path)
        if payload:
            rows.append(payload)
    return rows


def confidence(success: int, failure: int) -> float:
    total = success + failure
    if total <= 1:
        return 0.45 if success else 0.2
    return round(min(0.9, max(0.2, success / total * min(1.0, total / 4))), 3)


def mine_patterns(project: Path) -> dict[str, Any]:
    bundles = imported_bundles(project)
    counts: dict[str, dict[str, Any]] = {key: {'success': 0, 'failure': 0, 'evidence': []} for key in DEFAULT_PATTERNS}
    for bundle in bundles:
        artifacts = bundle.get('artifacts') or {}
        project_type = (bundle.get('fingerprint') or {}).get('project_type', 'unknown')
        for key, artifact in artifacts.items():
            surface = json.dumps(artifact, ensure_ascii=False).lower()
            if 'docs' in surface or 'readme' in surface or 'quickstart' in surface:
                counts['docs_cleanup_before_release']['success'] += 1
                counts['docs_cleanup_before_release']['evidence'].append(
                    {'project_id': bundle.get('project_id'), 'artifact': key}
                )
                counts['quickstart_before_public_release']['success'] += 1
            if 'test' in surface:
                counts['tests_before_refactor']['success'] += 1
                counts['tests_before_refactor']['evidence'].append(
                    {'project_id': bundle.get('project_id'), 'artifact': key}
                )
            if 'local_scanner' in surface or 'repo_scan' in surface:
                counts['local_scan_before_autopilot']['success'] += 1
                counts['local_scan_before_autopilot']['evidence'].append(
                    {'project_id': bundle.get('project_id'), 'artifact': key}
                )
            if 'cockpit' in surface:
                counts['cockpit_before_long_session']['success'] += 1
                counts['cockpit_before_long_session']['evidence'].append(
                    {'project_id': bundle.get('project_id'), 'artifact': key}
                )
            if 'worker_doctor' in surface or 'worker doctor' in surface:
                counts['worker_doctor_before_real_execution']['success'] += 1
                counts['worker_doctor_before_real_execution']['evidence'].append(
                    {'project_id': bundle.get('project_id'), 'artifact': key}
                )
            if 'no_delivery' in surface:
                counts['stop_on_no_delivery']['failure'] += 1
                counts['stop_on_no_delivery']['evidence'].append(
                    {'project_id': bundle.get('project_id'), 'artifact': key}
                )
            if 'blocked' in surface:
                counts['blocked_zone_requires_attention']['failure'] += 1
                counts['blocked_zone_requires_attention']['evidence'].append(
                    {'project_id': bundle.get('project_id'), 'artifact': key}
                )
        if project_type:
            counts['local_scan_before_autopilot']['evidence'].append(
                {'project_type': project_type, 'artifact': 'fingerprint'}
            )

    patterns = []
    for pattern_id, (action_type, why) in DEFAULT_PATTERNS.items():
        row = counts[pattern_id]
        success = int(row['success'])
        failure = int(row['failure'])
        evidence = row['evidence'][:8] or [
            {'source': 'default_template', 'basis': 'built-in release readiness pattern'}
        ]
        patterns.append(
            {
                'pattern_id': pattern_id,
                'project_type': 'mixed',
                'readiness_stage': 'release_candidate' if 'release' in pattern_id else 'unknown',
                'situation': pattern_id.replace('_', ' '),
                'recommended_next_action_type': action_type,
                'why_it_works': why,
                'evidence': evidence,
                'success_count': success,
                'failure_count': failure,
                'confidence': confidence(success, failure),
                'anti_patterns': ['pause_or_review_required'] if failure > success and failure else [],
            }
        )
    payload = {'generated_by': 'next_action_pattern_miner.py', 'patterns': patterns}
    return write_store(project, 'pattern_library', payload)


def main() -> int:
    parser = argparse.ArgumentParser(description='Mine evidence-backed next-action patterns.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = mine_patterns(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
