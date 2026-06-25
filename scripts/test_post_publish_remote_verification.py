#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from post_publish_remote_verifier import verify


def run(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(args, cwd=cwd, text=True, encoding='utf-8', errors='replace', capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(f'command failed {args}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc.stdout.strip()


def make_repo() -> tuple[Path, Path]:
    base = Path(tempfile.mkdtemp(prefix='post-verify-'))
    repo = base / 'repo'
    remote = base / 'remote.git'
    repo.mkdir()
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'test@example.local'], repo)
    run(['git', 'config', 'user.name', 'Test User'], repo)
    (repo / 'README.md').write_text('# Demo\n', encoding='utf-8')
    run(['git', 'add', 'README.md'], repo)
    run(['git', 'commit', '-m', 'base'], repo)
    run(['git', 'init', '--bare', str(remote)], base)
    run(['git', 'remote', 'add', 'origin', str(remote)], repo)
    run(['git', 'push', 'origin', 'master'], repo)
    (repo / 'README.md').write_text('# Demo\n\nReady.\n', encoding='utf-8')
    run(['git', 'add', 'README.md'], repo)
    run(['git', 'commit', '-m', 'local release content'], repo)
    run(['git', 'checkout', '-b', 'release/v1.0.0-alpha.1'], repo)
    run(['git', 'commit', '--allow-empty', '-m', 'remote equivalent release commit'], repo)
    run(['git', 'tag', '-a', 'v1.0.0-alpha.1', '-m', 'AI Project Operator v1.0.0-alpha.1'], repo)
    run(['git', 'push', 'origin', 'release/v1.0.0-alpha.1'], repo)
    run(['git', 'push', 'origin', 'v1.0.0-alpha.1'], repo)
    run(['git', 'checkout', 'master'], repo)
    run(
        ['git', 'fetch', 'origin', 'release/v1.0.0-alpha.1:refs/remotes/origin/release/v1.0.0-alpha.1', '--no-tags'],
        repo,
    )
    return repo, remote


def test_remote_verifier_equal_tree_different_sha() -> None:
    repo, remote = make_repo()
    before = run(['git', '--git-dir', str(remote), 'show-ref'], repo)
    payload = verify(repo, expected_tree='')
    after = run(['git', '--git-dir', str(remote), 'show-ref'], repo)
    assert payload['remote_verification_passed'] is True
    assert payload['remote_branch_exists'] is True
    assert payload['remote_tag_exists'] is True
    assert payload['tree_equal'] is True
    assert payload['local_remote_diff_empty'] is True
    assert payload['commit_sha_differs_but_tree_equal'] is True
    assert payload['unsafe_operation_performed'] is False
    assert before == after, 'verifier must not mutate remote refs'


def main() -> int:
    test_remote_verifier_equal_tree_different_sha()
    print('post publish remote verification tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
