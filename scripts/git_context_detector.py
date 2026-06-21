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


WINDOWS_ABS_RE = re.compile(r'^[A-Za-z]:[\\/]')
CREDENTIAL_REMOTE_RE = re.compile(r'^(https?://)([^/@\s]+@)(.+)$', re.IGNORECASE)
CREDENTIAL_PAIR_RE = re.compile(r'^(https?://)([^:/@\s]+:[^/@\s]+@)(.+)$', re.IGNORECASE)


def release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release'


def run_git(project: Path, args: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ['git', *args],
            cwd=project,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=8,
        )
        return proc.returncode, proc.stdout.rstrip('\r\n'), proc.stderr.rstrip('\r\n')
    except Exception as exc:
        return 1, '', str(exc)


def repo_relative(project: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project.resolve()).as_posix()
    except Exception:
        return path.name


def sanitize_remote(remote: str) -> tuple[str, bool, str]:
    raw = str(remote or '').strip()
    if not raw:
        return '', False, 'unknown'
    if WINDOWS_ABS_RE.match(raw) or raw.startswith('/') or raw.startswith('file:'):
        return '<local-remote>', False, 'other'
    redacted = CREDENTIAL_PAIR_RE.sub(r'\1<redacted>@\3', raw)
    redacted = CREDENTIAL_REMOTE_RE.sub(r'\1<redacted>@\3', redacted)
    provider = 'github' if 'github.com' in redacted.lower() else 'other'
    return redacted, redacted != raw, provider


def file_exists(project: Path, names: list[str]) -> bool:
    return any((project / name).exists() for name in names)


def find_repo_assets(project: Path) -> dict[str, Any]:
    workflow_files = []
    workflow_dir = project / '.github' / 'workflows'
    if workflow_dir.exists():
        for path in sorted([*workflow_dir.glob('*.yml'), *workflow_dir.glob('*.yaml')]):
            workflow_files.append(repo_relative(project, path))
    return {
        'readme': file_exists(project, ['README.md', 'README.rst', 'README.txt']),
        'license': file_exists(project, ['LICENSE', 'LICENSE.md', 'COPYING']),
        'changelog': file_exists(project, ['CHANGELOG.md', 'CHANGES.md', 'HISTORY.md']),
        'tests': (project / 'tests').exists() or any(project.glob('test_*.py')),
        'docs': (project / 'docs').exists() or file_exists(project, ['QUICKSTART.md', 'INSTALL.md']),
        'install': file_exists(project, ['INSTALL.md', 'pyproject.toml', 'package.json', 'requirements.txt']),
        'quickstart': file_exists(project, ['QUICKSTART.md']),
        'examples': (project / 'examples').exists() or file_exists(project, ['EXAMPLES.md']),
        'github_actions': workflow_files,
    }


def parse_status(project: Path, porcelain: str) -> tuple[int, int, int, list[str]]:
    staged = 0
    unstaged = 0
    untracked = 0
    files: list[str] = []
    for line in porcelain.splitlines():
        if not line:
            continue
        code = line[:2]
        path = line[3:].strip() if len(line) > 3 else ''
        if ' -> ' in path:
            path = path.split(' -> ', 1)[1].strip()
        path = path.replace('\\', '/')
        if path.startswith('.zoo-agent/'):
            continue
        if path and path not in files:
            files.append(path)
        if code == '??':
            untracked += 1
            continue
        if code[0] != ' ':
            staged += 1
        if code[1] != ' ':
            unstaged += 1
    return staged, unstaged, untracked, files[:80]


def detect_git_context(project: Path) -> dict[str, Any]:
    rc, inside, _ = run_git(project, ['rev-parse', '--is-inside-work-tree'])
    assets = find_repo_assets(project)
    if rc != 0 or inside.strip().lower() != 'true':
        payload = {
            'generated_by': 'git_context_detector.py',
            'generated_at': utc_now(),
            'is_git_repo': False,
            'current_branch': '',
            'default_branch_candidate': '',
            'working_tree_status': 'unknown',
            'changed_files_count': 0,
            'staged_files_count': 0,
            'unstaged_files_count': 0,
            'untracked_files_count': 0,
            'changed_files': [],
            'latest_commit': '',
            'remote': {'has_remote': False, 'provider': 'unknown', 'sanitized_remote': '', 'token_redacted': False},
            'github_actions': {'detected': bool(assets['github_actions']), 'workflow_files': assets['github_actions']},
            'repo_assets': {key: value for key, value in assets.items() if key != 'github_actions'},
        }
        write_json(release_dir(project) / 'git_context.json', payload)
        return payload

    _, branch, _ = run_git(project, ['branch', '--show-current'])
    if not branch:
        _, branch, _ = run_git(project, ['rev-parse', '--abbrev-ref', 'HEAD'])
    default_branch = ''
    _, origin_head, _ = run_git(project, ['symbolic-ref', '--quiet', '--short', 'refs/remotes/origin/HEAD'])
    if origin_head.startswith('origin/'):
        default_branch = origin_head.split('/', 1)[1]
    if not default_branch:
        default_branch = 'main' if (project / '.git').exists() else ''

    _, latest_commit, _ = run_git(project, ['rev-parse', '--short', 'HEAD'])
    _, status_text, _ = run_git(project, ['status', '--porcelain=v1'])
    staged, unstaged, untracked, files = parse_status(project, status_text)
    _, remote_raw, _ = run_git(project, ['remote', 'get-url', 'origin'])
    sanitized_remote, token_redacted, provider = sanitize_remote(remote_raw)
    payload = {
        'generated_by': 'git_context_detector.py',
        'generated_at': utc_now(),
        'is_git_repo': True,
        'current_branch': branch,
        'default_branch_candidate': default_branch,
        'working_tree_status': 'dirty' if status_text else 'clean',
        'changed_files_count': len(files),
        'staged_files_count': staged,
        'unstaged_files_count': unstaged,
        'untracked_files_count': untracked,
        'changed_files': files,
        'latest_commit': latest_commit,
        'remote': {
            'has_remote': bool(remote_raw),
            'provider': provider if remote_raw else 'unknown',
            'sanitized_remote': sanitized_remote,
            'token_redacted': token_redacted,
        },
        'github_actions': {'detected': bool(assets['github_actions']), 'workflow_files': assets['github_actions']},
        'repo_assets': {key: value for key, value in assets.items() if key != 'github_actions'},
    }
    write_json(release_dir(project) / 'git_context.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Detect local Git context without network access.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = detect_git_context(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
