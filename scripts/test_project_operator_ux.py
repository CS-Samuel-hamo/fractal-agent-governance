#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'


def run(cmd: list[str], cwd: Path, *, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if check and proc.returncode:
        raise AssertionError(f'command failed: {cmd}')
    return proc


def init_repo(env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix='project-operator-ux-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Operator UX\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'operator@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Operator UX Test'], repo, env=env)
    run(['git', 'add', 'README.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def assert_no_internal_leakage(text: str) -> None:
    lowered = text.lower()
    for term in [
        'eval',
        'governance',
        'planner',
        'verifier',
        'scheduler',
        'policy internals',
        'loop internals',
        'backend internals',
    ]:
        assert term not in lowered, f'public output leaked internal term: {term}'


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='operator-codex-home-')).resolve()))
    help_text = run([sys.executable, str(AGENT), '--help'], ROOT, env=env).stdout
    for visible in [
        'agent "<task>"',
        'agent start "<project goal>"',
        'agent status',
        'agent continue',
        'agent stop',
        'agent undo',
    ]:
        assert visible in help_text
    assert_no_internal_leakage(help_text)

    repo = init_repo(env)
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo, env=env)
    start = run(
        [sys.executable, str(AGENT), 'start', 'improve project readiness', '--workspace', str(repo)], repo, env=env
    ).stdout
    assert 'Done.' in start or 'Needs attention.' in start
    assert 'Undo:' in start or 'Suggested next step:' in start
    assert_no_internal_leakage(start)

    status = run([sys.executable, str(AGENT), 'status', '--workspace', str(repo), '--no-write'], repo, env=env).stdout
    assert '"mode": "status"' in status
    assert_no_internal_leakage(status)

    stopped = run([sys.executable, str(AGENT), 'stop', '--workspace', str(repo)], repo, env=env).stdout
    assert 'stopped' in stopped
    assert_no_internal_leakage(stopped)
    print('project operator ux tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
