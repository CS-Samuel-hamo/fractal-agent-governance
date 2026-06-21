#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json  # noqa: E402


PUBLIC_BRANCH = 'release/v1.0.0-alpha.1'
LOCAL_BRANCH = 'master'
FEEDBACK_DIR = Path('.zoo-agent') / 'feedback'
POSTLAUNCH_DOCS = ['POST_LAUNCH_STATUS.md', 'PUBLISHING.md', 'BRANCHING.md']


def run_git(project: Path, args: list[str], timeout: int = 45) -> dict[str, Any]:
    try:
        proc = subprocess.run(['git', *args], cwd=project, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return {'ok': proc.returncode == 0, 'returncode': proc.returncode, 'stdout': proc.stdout.strip(), 'stderr': proc.stderr.strip()}
    except Exception as exc:
        return {'ok': False, 'returncode': 1, 'stdout': '', 'stderr': str(exc)}


def rev(project: Path, ref: str) -> str:
    result = run_git(project, ['rev-parse', ref], timeout=10)
    return result['stdout'].splitlines()[0] if result.get('ok') and result.get('stdout') else ''


def file_exists_at_ref(project: Path, ref: str, path: str) -> bool:
    result = run_git(project, ['cat-file', '-e', f'{ref}:{path}'], timeout=10)
    return bool(result.get('ok'))


def preflight(project: Path, *, public_branch: str = PUBLIC_BRANCH, local_branch: str = LOCAL_BRANCH) -> dict[str, Any]:
    notes: list[str] = []
    remote_reachable = True
    fetch = run_git(project, ['fetch', 'origin', f'refs/heads/{public_branch}:refs/remotes/origin/{public_branch}', '--no-tags'], timeout=90)
    if not fetch.get('ok'):
        remote_reachable = False
        notes.append(f'read-only fetch inconclusive: {fetch.get("stderr")}')
    ls_remote = run_git(project, ['ls-remote', '--heads', 'origin', public_branch], timeout=45)
    if not ls_remote.get('ok'):
        remote_reachable = False
        notes.append(f'read-only ls-remote inconclusive: {ls_remote.get("stderr")}')

    local_commit = rev(project, local_branch) or rev(project, 'HEAD')
    remote_ref = f'origin/{public_branch}'
    remote_commit = rev(project, remote_ref)
    remote_branch_exists = bool(remote_commit or (ls_remote.get('ok') and ls_remote.get('stdout')))
    diff = run_git(project, ['diff', '--quiet', local_branch if rev(project, local_branch) else 'HEAD', remote_ref], timeout=20) if remote_commit else {'ok': False}
    diff_empty = bool(remote_commit and diff.get('ok'))
    remote_has_docs = bool(remote_commit and all(file_exists_at_ref(project, remote_ref, doc) for doc in POSTLAUNCH_DOCS))
    local_has_docs = all((project / doc).exists() for doc in POSTLAUNCH_DOCS)
    manual_sync = bool(local_has_docs and (not remote_has_docs or not diff_empty))
    suggested: list[str] = []
    if manual_sync:
        suggested = [
            f'git push origin HEAD:refs/heads/{public_branch}',
            'Then verify with: agent postlaunch --verify',
        ]
    payload = {
        'generated_at': utc_now(),
        'public_branch': public_branch,
        'local_branch': local_branch,
        'local_commit': local_commit,
        'remote_branch_exists': remote_branch_exists,
        'remote_reachable': remote_reachable,
        'remote_contains_postlaunch_docs': remote_has_docs,
        'local_contains_postlaunch_docs': local_has_docs,
        'local_remote_diff_empty': diff_empty,
        'manual_sync_recommended': manual_sync,
        'safe_sync_strategy': 'branch-aware no-force update' if manual_sync else 'none',
        'unsafe_commands_detected': any(' main' in cmd or '--force' in cmd or ' -f' in cmd for cmd in suggested),
        'suggested_manual_commands': suggested,
        'notes': notes,
    }
    write_json(project / FEEDBACK_DIR / 'public_branch_sync_preflight.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--public-branch', default=PUBLIC_BRANCH)
    args = parser.parse_args(argv)
    payload = preflight(project_root(args.workspace), public_branch=args.public_branch)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
