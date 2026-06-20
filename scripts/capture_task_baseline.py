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

from runtime_common import project_root, safe_name, utc_now, write_json  # noqa: E402


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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout if proc.returncode == 0 else ''


def parse_status_path(line: str) -> str:
    path = line[3:].strip() if len(line) > 3 else line.strip()
    if ' -> ' in path:
        path = path.split(' -> ', 1)[1]
    return path.strip('"').replace('\\', '/')


def status_paths(status_lines: list[str]) -> list[str]:
    paths = []
    for line in status_lines:
        if line.strip():
            path = parse_status_path(line)
            if path:
                paths.append(path)
    return sorted(set(paths))


def matches_any(path: str, patterns: list[str]) -> bool:
    normalized = path.replace('\\', '/')
    return any(fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch('/' + normalized, pattern) for pattern in patterns)


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


def hash_paths(workspace: Path, paths: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    hashes: dict[str, str] = {}
    skipped: dict[str, str] = {}
    for rel in sorted(set(paths)):
        target = workspace / rel
        if not target.exists() or not target.is_file():
            continue
        skip, reason = should_skip_content(rel, target)
        if skip:
            skipped[rel] = reason
            continue
        try:
            hashes[rel] = sha256_file(target)
        except OSError:
            skipped[rel] = 'skipped_read_error'
    return hashes, skipped


def exact_allowed_paths(values: list[str]) -> list[str]:
    exact = []
    for value in values:
        normalized = value.replace('\\', '/').strip()
        if normalized and not any(ch in normalized for ch in '*?[]'):
            exact.append(normalized)
    return exact


def capture(args: argparse.Namespace) -> dict[str, Any]:
    workspace = project_root(args.workspace)
    status = [line for line in run_git(['status', '--porcelain=v1', '-uall'], workspace).splitlines() if line.strip()]
    diff_name_only = sorted(
        set(
            line.strip().replace('\\', '/')
            for command in [['diff', '--name-only'], ['diff', '--cached', '--name-only']]
            for line in run_git(command, workspace).splitlines()
            if line.strip()
        )
    )
    untracked = sorted(parse_status_path(line) for line in status if line.startswith('??') and parse_status_path(line))
    tracked_paths = sorted(line.strip().replace('\\', '/') for line in run_git(['ls-files'], workspace).splitlines() if line.strip())
    baseline_paths = sorted(set(status_paths(status) + diff_name_only + untracked + exact_allowed_paths(args.allowed_file or [])))
    file_hashes, skipped_hashes = hash_paths(workspace, baseline_paths)

    payload = {
        'schema_version': '1.0',
        'generated_by': 'capture_task_baseline.py',
        'run_id': args.run_id,
        'task_id': args.task_id,
        'workspace': str(workspace),
        'created_at': utc_now(),
        'git_head': run_git(['rev-parse', 'HEAD'], workspace).strip(),
        'git_branch': run_git(['branch', '--show-current'], workspace).strip(),
        'status_porcelain': status,
        'diff_name_only': diff_name_only,
        'untracked_files': untracked,
        'file_hashes': file_hashes,
        'skipped_hashes': skipped_hashes,
        'tracked_paths': tracked_paths,
        'baseline_scope': {
            'allowed_files': args.allowed_file or [],
            'denied_files': args.denied_file or [],
            'task_type': args.task_type,
            'route': args.route,
            'input_text': args.input_text,
        },
    }
    output = Path(args.output).resolve() if args.output else workspace / '.zoo-agent' / 'runs' / args.run_id / 'tasks' / safe_name(args.task_id) / 'task-baseline.json'
    write_json(output, payload)
    payload['path'] = str(output)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Capture the pre-execution task baseline for delivery outcome checks.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--output', default='')
    parser.add_argument('--route', default='')
    parser.add_argument('--task-type', default='')
    parser.add_argument('--input-text', default='')
    parser.add_argument('--allowed-file', action='append', default=[])
    parser.add_argument('--denied-file', action='append', default=[])
    args = parser.parse_args()
    payload = capture(args)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
