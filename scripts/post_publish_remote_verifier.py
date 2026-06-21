#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json  # noqa: E402


EXPECTED_BRANCH = 'release/v1.0.0-alpha.1'
EXPECTED_TAG = 'v1.0.0-alpha.1'
EXPECTED_TREE = '64a3705393a9acdf36dc3e7f486c2ff8f78590c1'
LOCAL_BRANCH = 'master'
POST_LAUNCH_DIR = Path('.zoo-agent') / 'post_launch'


def run_git(project: Path, args: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ['git', *args],
            cwd=project,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return {'ok': proc.returncode == 0, 'returncode': proc.returncode, 'stdout': proc.stdout.strip(), 'stderr': proc.stderr.strip()}
    except Exception as exc:
        return {'ok': False, 'returncode': 1, 'stdout': '', 'stderr': str(exc)}


def sanitize_remote(value: str) -> str:
    value = value.strip()
    value = re.sub(r'(https?://)([^/@:\s]+):([^/@\s]+)@', r'\1<redacted>@', value)
    value = re.sub(r'(https?://)([^/@\s]+)@', r'\1<redacted>@', value)
    return value


def _first_remote(project: Path) -> str:
    remotes = run_git(project, ['remote', '-v'])
    for line in remotes.get('stdout', '').splitlines():
        if line.startswith('origin') and '(fetch)' in line:
            parts = line.split()
            if len(parts) >= 2:
                return sanitize_remote(parts[1])
    return ''


def _rev(project: Path, rev: str) -> str:
    result = run_git(project, ['rev-parse', rev], timeout=10)
    return result['stdout'].splitlines()[0] if result.get('ok') and result.get('stdout') else ''


def _remote_ref_exists(project: Path, kind: str, name: str) -> tuple[bool, str]:
    args = ['ls-remote', '--heads' if kind == 'head' else '--tags', 'origin', name]
    result = run_git(project, args, timeout=45)
    if not result.get('ok'):
        return False, result.get('stderr') or 'remote query failed'
    return bool(result.get('stdout')), ''


def verify(project: Path, *, expected_branch: str = EXPECTED_BRANCH, expected_tag: str = EXPECTED_TAG, expected_tree: str = EXPECTED_TREE, local_branch: str = LOCAL_BRANCH) -> dict[str, Any]:
    notes: list[str] = []
    inconclusive = False
    repo = _first_remote(project)
    branch_result = run_git(project, ['branch', '--show-current'], timeout=10)
    current_branch = branch_result.get('stdout') or local_branch

    fetch = run_git(project, ['fetch', 'origin', f'refs/heads/{expected_branch}:refs/remotes/origin/{expected_branch}', '--no-tags'], timeout=90)
    if not fetch.get('ok'):
        inconclusive = True
        notes.append('remote branch fetch failed; using any existing local remote ref if available')

    remote_branch_exists, branch_error = _remote_ref_exists(project, 'head', expected_branch)
    remote_tag_exists, tag_error = _remote_ref_exists(project, 'tag', expected_tag)
    if branch_error:
        inconclusive = True
        notes.append(f'remote branch query inconclusive: {branch_error}')
        remote_branch_exists = bool(_rev(project, f'origin/{expected_branch}'))
    if tag_error:
        inconclusive = True
        notes.append(f'remote tag query inconclusive: {tag_error}')
        remote_tag_exists = bool(_rev(project, f'refs/tags/{expected_tag}'))
        if remote_tag_exists:
            notes.append('used locally synchronized tag ref after remote tag query failed')

    local_ref = local_branch if _rev(project, local_branch) else 'HEAD'
    remote_ref = f'origin/{expected_branch}'
    local_tree = _rev(project, f'{local_ref}^{{tree}}')
    remote_tree = _rev(project, f'{remote_ref}^{{tree}}')
    local_commit = _rev(project, local_ref)
    remote_commit = _rev(project, remote_ref)

    diff = run_git(project, ['diff', '--quiet', local_ref, remote_ref], timeout=20) if remote_commit else {'ok': False}
    local_remote_diff_empty = bool(remote_commit and diff.get('ok'))
    tree_equal = bool(local_tree and remote_tree and local_tree == remote_tree)
    if expected_tree and local_tree and local_tree != expected_tree:
        notes.append('local tree differs from recorded expected tree')
    if expected_tree and remote_tree and remote_tree != expected_tree:
        notes.append('remote tree differs from recorded expected tree')
    sha_differs_tree_equal = bool(local_commit and remote_commit and local_commit != remote_commit and tree_equal)
    if sha_differs_tree_equal:
        notes.append('content_verified_with_different_commit_sha')

    passed = bool(remote_branch_exists and remote_tag_exists and local_remote_diff_empty and tree_equal)
    if inconclusive and tree_equal and local_remote_diff_empty:
        notes.append('remote_verification_inconclusive_but_content_status_documented')

    payload = {
        'generated_at': utc_now(),
        'remote_verification_passed': passed,
        'remote_verification_inconclusive': inconclusive,
        'repo': repo,
        'expected_branch': expected_branch,
        'expected_tag': expected_tag,
        'local_branch': current_branch,
        'remote_branch_exists': remote_branch_exists,
        'remote_tag_exists': remote_tag_exists,
        'local_remote_diff_empty': local_remote_diff_empty,
        'tree_equal': tree_equal,
        'local_tree': local_tree,
        'remote_tree': remote_tree,
        'local_commit': local_commit,
        'remote_commit': remote_commit,
        'commit_sha_differs_but_tree_equal': sha_differs_tree_equal,
        'github_release_object_verified': False,
        'tag_page_available_or_assumed': remote_tag_exists,
        'unsafe_operation_performed': False,
        'notes': notes,
    }
    write_json(project / POST_LAUNCH_DIR / 'remote_publish_verification.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--expected-branch', default=EXPECTED_BRANCH)
    parser.add_argument('--expected-tag', default=EXPECTED_TAG)
    parser.add_argument('--expected-tree', default=EXPECTED_TREE)
    args = parser.parse_args(argv)
    payload = verify(project_root(args.workspace), expected_branch=args.expected_branch, expected_tag=args.expected_tag, expected_tree=args.expected_tree)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('remote_verification_passed') or payload.get('tree_equal') else 1


if __name__ == '__main__':
    raise SystemExit(main())
