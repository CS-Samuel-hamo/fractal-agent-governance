#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, write_json

CODE_SUFFIXES = ('.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.java', '.cs', '.cpp', '.c', '.h')
TEST_MARKERS = ('tests/', 'test/', '_test.', '.test.', '.spec.')
DOC_SUFFIXES = ('.md', '.mdx', '.rst', '.txt')


def normalize_files(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).replace('\\', '/') for item in values if str(item or '').strip()]


def infer_task_type(title: str, target_files: list[str]) -> str:
    surface = ' '.join([title, *target_files]).lower()
    if any(
        term in surface for term in ['secret', '.env', 'payment', 'auth', 'database migration', 'production deploy']
    ):
        return 'unknown'
    if any(path.startswith('docs/') or path == 'README.md' or path.endswith(DOC_SUFFIXES) for path in target_files):
        return 'docs_update'
    if any(any(marker in path for marker in TEST_MARKERS) for path in target_files):
        return 'test_update'
    if any(term in surface for term in ['repo scan', 'scan repo', 'project map', 'map refresh']):
        return 'repo_scan'
    if any(term in surface for term in ['readiness', 'release']):
        return 'release_readiness'
    if any(term in surface for term in ['refactor', 'cross-module', 'public api', 'schema']):
        return 'refactor'
    if any(path.endswith(CODE_SUFFIXES) for path in target_files):
        return 'code_edit'
    if any(term in surface for term in ['analyze', 'review', 'explain']):
        return 'analysis'
    return 'unknown'


def complexity(target_files: list[str], title: str) -> str:
    if len(target_files) > 5 or any(term in title.lower() for term in ['cross-module', 'large', 'project-wide']):
        return 'large'
    if len(target_files) > 1 or any(term in title.lower() for term in ['refactor', 'format']):
        return 'medium'
    return 'small'


def preferred_type(task_type: str) -> str:
    if task_type == 'docs_update':
        return 'docs'
    if task_type == 'test_update':
        return 'test'
    if task_type in {'code_edit', 'refactor'}:
        return 'code'
    if task_type in {'repo_scan', 'analysis', 'release_readiness'}:
        return 'analysis'
    return 'dry_run'


def classify_task_profile(action: dict[str, Any], *, session_state: dict[str, Any] | None = None) -> dict[str, Any]:
    target_files = normalize_files(action.get('target_files') or action.get('allowed_files') or [])
    title = str(action.get('title') or action.get('objective') or action.get('selected_action_id') or '')
    risk = str(action.get('risk_level') or 'unknown').lower()
    if risk not in {'low', 'medium', 'high'}:
        risk = 'unknown'
    trust_zone = str(action.get('trust_zone') or '').lower() or ('trusted' if risk == 'low' else 'guarded')
    execution_mode = str(action.get('execution_mode') or '').lower()
    task_type = infer_task_type(title, target_files)
    requires_actual = execution_mode == 'auto' and trust_zone != 'blocked'
    if task_type in {'repo_scan', 'analysis', 'release_readiness'}:
        requires_actual = False
    if trust_zone == 'blocked':
        requires_actual = False
    profile = {
        'schema_version': '1.0',
        'generated_by': 'task_profile_classifier.py',
        'task_id': str(action.get('selected_action_id') or action.get('action_id') or action.get('leaf_id') or 'task'),
        'title': title,
        'task_type': task_type,
        'risk_level': risk,
        'trust_zone': trust_zone,
        'requires_actual_execution': bool(requires_actual),
        'requires_command_execution': task_type in {'test_update', 'refactor'} and requires_actual,
        'requires_long_context': complexity(target_files, title) == 'large',
        'target_files': target_files,
        'estimated_complexity': complexity(target_files, title),
        'preferred_worker_type': preferred_type(task_type),
        'session_id': str((session_state or {}).get('session_id') or ''),
    }
    return profile


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify a map action for worker routing.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--action', required=True)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    action = load_json(Path(args.action).resolve())
    payload = classify_task_profile(action)
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'workers' / 'task_profile.json'
    write_json(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
