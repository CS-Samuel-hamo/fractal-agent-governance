#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, safe_name, utc_now, write_json

RUNTIME_PATTERNS = [
    '.zoo-agent/**',
    '.tmp/**',
]
GOVERNANCE_PATTERNS = [
    'AGENTS.md',
    'AGENTS.md.new',
    '.gitignore.agent.patch',
    '.roo/rules/**',
    '.roo/rules.new/**',
    'bootstrap-report.md',
    'project-profile.json',
    'project-readiness.json',
]
IGNORED_GENERATED_PATTERNS = [
    '__pycache__/**',
    '**/__pycache__/**',
    '.pytest_cache/**',
    '**/.pytest_cache/**',
    '*.pyc',
    '**/*.pyc',
]
SECRET_PATTERNS = [
    '.env',
    '.env.*',
    '**/.env',
    '**/.env.*',
    '**/*.pem',
    '**/*.key',
    '**/*secret*',
    '**/*token*',
    '**/*credential*',
    'secrets/**',
    'credentials/**',
    '.codex/**',
]
MAX_HASH_BYTES = 2 * 1024 * 1024


def run_git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        ['git', *args],
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    return proc.stdout if proc.returncode == 0 else ''


def parse_status_path(line: str) -> str:
    path = line[3:].strip() if len(line) > 3 else line.strip()
    if ' -> ' in path:
        path = path.split(' -> ', 1)[1]
    return path.strip('"').replace('\\', '/')


def status_paths(lines: list[str]) -> list[str]:
    return sorted(set(path for line in lines if (path := parse_status_path(line))))


def matches_any(path: str, patterns: list[str]) -> bool:
    normalized = path.replace('\\', '/')
    return any(
        fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch('/' + normalized, pattern) for pattern in patterns
    )


def should_skip_content(path: str, absolute: Path) -> tuple[bool, str]:
    if matches_any(path, SECRET_PATTERNS):
        return True, 'skipped_secret_like_path'
    try:
        if absolute.is_file() and absolute.stat().st_size > MAX_HASH_BYTES:
            return True, 'skipped_large_file'
    except OSError:
        return True, 'skipped_stat_error'
    return False, ''


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def file_hash(workspace: Path, rel: str) -> tuple[str, str]:
    target = workspace / rel
    if not target.exists() or not target.is_file():
        return '', 'missing_or_not_file'
    skip, reason = should_skip_content(rel, target)
    if skip:
        return '', reason
    try:
        return sha256_file(target), ''
    except OSError:
        return '', 'skipped_read_error'


def current_changed_paths(workspace: Path) -> tuple[list[str], list[str], list[str]]:
    status = [line for line in run_git(['status', '--porcelain=v1', '-uall'], workspace).splitlines() if line.strip()]
    diff = sorted(
        set(
            line.strip().replace('\\', '/')
            for command in [['diff', '--name-only'], ['diff', '--cached', '--name-only']]
            for line in run_git(command, workspace).splitlines()
            if line.strip()
        )
    )
    untracked = sorted(parse_status_path(line) for line in status if line.startswith('??') and parse_status_path(line))
    paths = sorted(set(status_paths(status) + diff + untracked))
    return status, diff, paths


def classify_task_file(
    path: str,
    *,
    runtime_artifacts: list[str],
    governance_artifacts: list[str],
    ignored_generated_files: list[str],
    business_candidate_files: list[str],
) -> None:
    if matches_any(path, RUNTIME_PATTERNS):
        runtime_artifacts.append(path)
    elif matches_any(path, IGNORED_GENERATED_PATTERNS):
        ignored_generated_files.append(path)
    elif matches_any(path, GOVERNANCE_PATTERNS):
        governance_artifacts.append(path)
    else:
        business_candidate_files.append(path)


def compare(args: argparse.Namespace) -> dict[str, Any]:
    baseline_path = Path(args.baseline).resolve()
    baseline = load_json(baseline_path)
    if not baseline:
        raise SystemExit(f'Missing or invalid baseline: {baseline_path}')
    workspace = project_root(args.workspace or baseline.get('workspace') or '.')
    status, diff, current_paths = current_changed_paths(workspace)
    baseline_status_paths = set(status_paths([str(line) for line in baseline.get('status_porcelain') or []]))
    baseline_diff = set(str(item).replace('\\', '/') for item in baseline.get('diff_name_only') or [])
    baseline_untracked = set(str(item).replace('\\', '/') for item in baseline.get('untracked_files') or [])
    baseline_existing_diff = baseline_status_paths | baseline_diff | baseline_untracked
    tracked_paths = set(str(item).replace('\\', '/') for item in baseline.get('tracked_paths') or [])
    baseline_hashes = {str(k).replace('\\', '/'): str(v) for k, v in (baseline.get('file_hashes') or {}).items()}
    baseline_skipped = {str(k).replace('\\', '/'): str(v) for k, v in (baseline.get('skipped_hashes') or {}).items()}
    denied_patterns = [str(item) for item in (baseline.get('baseline_scope') or {}).get('denied_files') or []]
    denied_patterns.extend(args.denied_file or [])

    changed_since_baseline: list[str] = []
    new_since_baseline: list[str] = []
    deleted_since_baseline: list[str] = []
    unchanged_existing_diff: list[str] = []
    notes: list[str] = []

    for path in current_paths:
        exists_at_baseline = (
            path in tracked_paths
            or path in baseline_existing_diff
            or path in baseline_hashes
            or path in baseline_skipped
        )
        if path in baseline_existing_diff:
            before_hash = baseline_hashes.get(path, '')
            after_hash, skip_reason = file_hash(workspace, path)
            if before_hash and after_hash and before_hash != after_hash:
                changed_since_baseline.append(path)
            elif before_hash and after_hash and before_hash == after_hash:
                unchanged_existing_diff.append(path)
            elif path in baseline_skipped:
                unchanged_existing_diff.append(path)
                notes.append(
                    f'{path}: baseline hash skipped ({baseline_skipped[path]}); treated as pre-existing diff unless later classified unsafe.'
                )
            elif skip_reason == 'missing_or_not_file':
                deleted_since_baseline.append(path)
            else:
                unchanged_existing_diff.append(path)
        elif exists_at_baseline:
            changed_since_baseline.append(path)
        else:
            new_since_baseline.append(path)

    for path in sorted((tracked_paths | baseline_existing_diff) - set(current_paths)):
        if path in baseline_existing_diff and not (workspace / path).exists():
            deleted_since_baseline.append(path)

    runtime_artifacts: list[str] = []
    governance_artifacts: list[str] = []
    business_candidate_files: list[str] = []
    ignored_generated_files: list[str] = []
    denied_files_touched: list[str] = []
    for path in sorted(set(changed_since_baseline + new_since_baseline + deleted_since_baseline)):
        classify_task_file(
            path,
            runtime_artifacts=runtime_artifacts,
            governance_artifacts=governance_artifacts,
            ignored_generated_files=ignored_generated_files,
            business_candidate_files=business_candidate_files,
        )
        if denied_patterns and matches_any(path, denied_patterns):
            denied_files_touched.append(path)

    payload = {
        'schema_version': '1.0',
        'generated_by': 'compare_task_baseline.py',
        'run_id': str(baseline.get('run_id') or args.run_id),
        'task_id': str(baseline.get('task_id') or args.task_id),
        'workspace': str(workspace),
        'baseline_path': str(baseline_path),
        'created_at': utc_now(),
        'current_status_porcelain': status,
        'current_diff_name_only': diff,
        'changed_since_baseline': sorted(set(changed_since_baseline)),
        'new_since_baseline': sorted(set(new_since_baseline)),
        'deleted_since_baseline': sorted(set(deleted_since_baseline)),
        'unchanged_existing_diff': sorted(set(unchanged_existing_diff)),
        'runtime_artifacts': sorted(set(runtime_artifacts)),
        'governance_artifacts': sorted(set(governance_artifacts)),
        'business_candidate_files': sorted(set(business_candidate_files)),
        'ignored_generated_files': sorted(set(ignored_generated_files)),
        'denied_files_touched': sorted(set(denied_files_touched)),
        'notes': notes,
    }
    output = (
        Path(args.output).resolve()
        if args.output
        else workspace
        / '.zoo-agent'
        / 'runs'
        / payload['run_id']
        / 'tasks'
        / safe_name(payload['task_id'])
        / 'task-delta.json'
    )
    write_json(output, payload)
    payload['path'] = str(output)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Compare a task baseline with post-execution workspace state.')
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--workspace', default='')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--task-id', default='')
    parser.add_argument('--output', default='')
    parser.add_argument('--denied-file', action='append', default=[])
    args = parser.parse_args()
    payload = compare(args)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if payload['denied_files_touched'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
