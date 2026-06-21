#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_branch_sync_preflight import preflight  # noqa: E402


def run(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(args, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise AssertionError(f'command failed {args}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc.stdout.strip()


def make_repo() -> tuple[Path, Path]:
    base = Path(tempfile.mkdtemp(prefix='feedback-sync-'))
    repo = base / 'repo'
    remote = base / 'remote.git'
    repo.mkdir()
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'sync@example.local'], repo)
    run(['git', 'config', 'user.name', 'Sync Test'], repo)
    (repo / 'README.md').write_text('# Demo\n', encoding='utf-8')
    run(['git', 'add', 'README.md'], repo)
    run(['git', 'commit', '-m', 'base'], repo)
    run(['git', 'init', '--bare', str(remote)], base)
    run(['git', 'remote', 'add', 'origin', str(remote)], repo)
    run(['git', 'checkout', '-b', 'release/v1.0.0-alpha.1'], repo)
    run(['git', 'push', 'origin', 'release/v1.0.0-alpha.1'], repo)
    run(['git', 'checkout', 'master'], repo)
    (repo / 'PUBLISHING.md').write_text('# Publishing\n', encoding='utf-8')
    (repo / 'BRANCHING.md').write_text('# Branching\n', encoding='utf-8')
    (repo / 'POST_LAUNCH_STATUS.md').write_text('# Status\n', encoding='utf-8')
    run(['git', 'add', 'PUBLISHING.md', 'BRANCHING.md', 'POST_LAUNCH_STATUS.md'], repo)
    run(['git', 'commit', '-m', 'add postlaunch docs locally'], repo)
    return repo, remote


def test_sync_preflight_local_ahead_no_unsafe_commands() -> None:
    repo, remote = make_repo()
    before = run(['git', '--git-dir', str(remote), 'show-ref'], repo)
    payload = preflight(repo)
    after = run(['git', '--git-dir', str(remote), 'show-ref'], repo)
    assert payload['remote_branch_exists'] is True
    assert payload['remote_contains_postlaunch_docs'] is False
    assert payload['manual_sync_recommended'] is True
    assert payload['unsafe_commands_detected'] is False
    assert all(' main' not in cmd for cmd in payload['suggested_manual_commands'])
    assert all('--force' not in cmd and ' -f' not in cmd for cmd in payload['suggested_manual_commands'])
    assert before == after, 'preflight must not mutate remote refs'


def main() -> int:
    test_sync_preflight_local_ahead_no_unsafe_commands()
    print('public branch sync preflight tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
