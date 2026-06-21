#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from branch_hygiene_audit import audit  # noqa: E402
from default_branch_advisor import advise  # noqa: E402
from publishing_command_linter import lint_texts  # noqa: E402


def run(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(args, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise AssertionError(f'command failed {args}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc.stdout.strip()


def init_repo(path: Path, content: str) -> None:
    path.mkdir()
    run(['git', 'init'], path)
    run(['git', 'config', 'user.email', 'test@example.local'], path)
    run(['git', 'config', 'user.name', 'Test User'], path)
    (path / 'README.md').write_text(content, encoding='utf-8')
    run(['git', 'add', 'README.md'], path)
    run(['git', 'commit', '-m', 'init'], path)


def repo_with_unrelated_origin_master() -> Path:
    base = Path(tempfile.mkdtemp(prefix='branch-hygiene-'))
    local = base / 'local'
    seed = base / 'seed'
    remote = base / 'remote.git'
    init_repo(local, '# Local\n')
    init_repo(seed, '# Remote\n')
    run(['git', 'init', '--bare', str(remote)], base)
    run(['git', 'remote', 'add', 'origin', str(remote)], seed)
    run(['git', 'push', 'origin', 'master'], seed)
    run(['git', 'remote', 'add', 'origin', str(remote)], local)
    run(['git', 'fetch', 'origin', '--no-tags'], local)
    return local


def test_linter_detects_bad_commands() -> None:
    payload = lint_texts({'bad.md': 'git push origin main\ngit push --force origin master\ngh pr create\n'})
    assert payload['hardcoded_main_push_detected'] is True
    assert payload['force_push_detected'] is True
    assert payload['unsafe_github_write_detected'] is True
    assert payload['publishing_command_lint_passed'] is False


def test_branch_hygiene_detects_missing_main_and_force_risk() -> None:
    repo = repo_with_unrelated_origin_master()
    payload = audit(repo)
    assert payload['main_exists'] is False
    assert payload['master_exists'] is True
    assert payload['master_fast_forward_safe'] is False
    assert payload['force_push_risk'] == 'high'


def test_default_branch_advisor_is_manual_only() -> None:
    repo = repo_with_unrelated_origin_master()
    payload = advise(repo)
    assert payload['automated_change_performed'] is False
    assert any('Settings' in step for step in payload['manual_steps'])


def main() -> int:
    test_linter_detects_bad_commands()
    test_branch_hygiene_detects_missing_main_and_force_risk()
    test_default_branch_advisor_is_manual_only()
    print('branch hygiene publishing tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
