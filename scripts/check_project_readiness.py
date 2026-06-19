#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from shutil import which
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json  # noqa: E402


UNTRACKED_BLOCK_THRESHOLD = 1000
KNOWN_BLOCKER_TYPES = [
    'dirty_worktree',
    'unborn_repo',
    'nested_git_repo',
    'initial_commit_timeout',
    'stale_git_index_lock',
    'missing_git_repo',
    'codex_unavailable',
    'codex_home_unavailable',
    'test_command_unknown',
    'large_untracked_set',
    'bootstrap_file_conflict',
    'unsafe_existing_state',
]


def run_git(args: list[str], cwd: Path, *, timeout: int = 15) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ['git', *args],
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}
    except subprocess.TimeoutExpired:
        return {'returncode': 124, 'stdout': '', 'stderr': 'git command timed out'}


def add_blocker(blockers: list[dict[str, Any]], kind: str, severity: str, message: str, action: str, *, auto_fix: bool = False) -> None:
    blockers.append(
        {
            'type': kind,
            'severity': severity,
            'message': message,
            'recommended_action': action,
            'auto_fix_available': auto_fix,
        }
    )


def has_git_head(repo: Path) -> bool:
    return run_git(['rev-parse', '--verify', 'HEAD'], repo).get('returncode') == 0


def status_lines(repo: Path) -> list[str]:
    status = run_git(['status', '--short', '-uall'], repo)
    if status.get('returncode') != 0:
        return []
    return [line for line in str(status.get('stdout') or '').splitlines() if line.strip()]


def is_known_runtime_or_proposal(path: str) -> bool:
    normalized = path.replace('\\', '/')
    return (
        normalized.startswith('.zoo-agent/')
        or normalized == 'AGENTS.md.new'
        or normalized == '.gitignore.agent.patch'
        or normalized.startswith('.roo/rules.new/')
    )


def nested_git_dirs(repo: Path) -> list[str]:
    nested: list[str] = []
    skip_dirs = {'.git', '.zoo-agent', '__pycache__', '.pytest_cache', 'node_modules', '.venv', 'venv'}
    for root, dirs, _files in os.walk(repo):
        original_dirs = list(dirs)
        for dirname in original_dirs:
            if dirname == '.git':
                nested_path = Path(root) / dirname
                if nested_path.resolve() != (repo / '.git').resolve():
                    nested.append(str(nested_path.relative_to(repo)).replace('\\', '/'))
        dirs[:] = [d for d in dirs if d not in skip_dirs]
    return sorted(nested)


def analyze_project_readiness(workspace: Path | str, *, assume_codex_home: str = '') -> dict[str, Any]:
    project = project_root(workspace)
    blockers: list[dict[str, Any]] = []
    git_probe = run_git(['rev-parse', '--show-toplevel'], project)
    git_repo = git_probe.get('returncode') == 0
    repo = Path(str(git_probe.get('stdout') or '').strip()).resolve() if git_repo and git_probe.get('stdout') else project

    if not git_repo:
        add_blocker(
            blockers,
            'missing_git_repo',
            'blocking',
            'Workspace is not a git repository.',
            'Run agent bootstrap in an empty directory or initialize git explicitly for a new project.',
        )
    else:
        if not has_git_head(repo):
            add_blocker(
                blockers,
                'unborn_repo',
                'blocking',
                'Git repository has no initial commit.',
                'Create an explicit initial commit after reviewing files; bootstrap will not add all or commit automatically.',
            )
        lines = status_lines(repo)
        user_dirty = [line for line in lines if not is_known_runtime_or_proposal(line[3:].strip().strip('"'))]
        if user_dirty:
            add_blocker(
                blockers,
                'dirty_worktree',
                'blocking',
                'Workspace has uncommitted or untracked non-runtime files.',
                'Commit or stash changes yourself before running real Codex execution.',
            )
        untracked = [line for line in lines if line.startswith('??')]
        if len(untracked) >= UNTRACKED_BLOCK_THRESHOLD:
            add_blocker(
                blockers,
                'large_untracked_set',
                'blocking',
                f'Workspace has {len(untracked)} untracked files.',
                'Review .gitignore and commit/stash intentionally; bootstrap will not git add all.',
            )
        elif len(untracked) >= 100:
            add_blocker(
                blockers,
                'large_untracked_set',
                'warning',
                f'Workspace has {len(untracked)} untracked files.',
                'Review .gitignore before actual execution.',
            )
        nested = nested_git_dirs(repo)
        if nested:
            add_blocker(
                blockers,
                'nested_git_repo',
                'blocking',
                'Nested git repositories were found.',
                'Decide whether they are submodules, should be ignored, or should have nested .git removed manually.',
            )
            blockers[-1]['paths'] = nested
        index_lock = repo / '.git' / 'index.lock'
        if index_lock.exists():
            add_blocker(
                blockers,
                'stale_git_index_lock',
                'blocking',
                'A git index.lock file exists.',
                'Verify no git process is running before removing the lock manually.',
            )

    codex_home = assume_codex_home or os.environ.get('CODEX_HOME', '')
    if not codex_home:
        add_blocker(
            blockers,
            'codex_home_unavailable',
            'warning',
            'CODEX_HOME is not set.',
            'Set CODEX_HOME before real Codex execution.',
        )
    codex_path = which('codex')
    if not codex_path:
        add_blocker(
            blockers,
            'codex_unavailable',
            'warning',
            'Codex CLI was not found on PATH.',
            'Install or expose Codex CLI before actual worker execution.',
        )

    blocking = [item for item in blockers if item.get('severity') == 'blocking']
    warnings = [item for item in blockers if item.get('severity') == 'warning']
    payload = {
        'schema_version': '1.0',
        'generated_by': 'check_project_readiness.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'safe_for_bootstrap': not any(item['type'] in {'missing_git_repo', 'nested_git_repo', 'stale_git_index_lock'} and item['severity'] == 'blocking' for item in blockers),
        'safe_for_level_0_1_trial': not blocking,
        'safe_for_codex_actual_run': not blocking and bool(codex_path),
        'blockers': blockers,
        'known_blocker_types': KNOWN_BLOCKER_TYPES,
        'blocking_issues': [item['type'] for item in blocking],
        'warnings': [item['type'] for item in warnings],
        'next_actions': [item['recommended_action'] for item in blockers] or ['Run a bounded dry-run before actual Codex execution.'],
        'git': {
            'is_repo': git_repo,
            'repo_root': str(repo) if git_repo else '',
            'has_head': has_git_head(repo) if git_repo else False,
            'status_entry_count': len(status_lines(repo)) if git_repo else 0,
        },
        'codex_cli_detected': bool(codex_path),
        'codex_home_available': bool(codex_home),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify project readiness blockers for local alpha runs.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--codex-home', default='')
    parser.add_argument('--output', default='')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()

    payload = analyze_project_readiness(args.workspace, assume_codex_home=args.codex_home)
    output = Path(args.output).resolve() if args.output else Path(args.workspace).resolve() / '.zoo-agent' / 'project-readiness.json'
    if args.write or args.output:
        write_json(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload['safe_for_level_0_1_trial'] else 10


if __name__ == '__main__':
    raise SystemExit(main())
