#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'


def run(cmd: list[str], cwd: Path, *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
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
    if proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def init_repo(env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix='session-cockpit-sync-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Session Cockpit\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'sync@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Cockpit Sync Test'], repo, env=env)
    run(['git', 'add', 'README.md', 'docs/guide.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def assert_no_internal(text: str) -> None:
    lowered = text.lower()
    for term in ['eval', 'governance', 'planner', 'verifier', 'scheduler', 'backend internals']:
        assert term not in lowered, f'internal term leaked: {term}'


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='session-sync-codex-home-')).resolve()))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)
    repo = init_repo(env)
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo, env=env)
    run(
        [sys.executable, str(AGENT), 'start', 'prepare this project for public release', '--workspace', str(repo)],
        repo,
        env=env,
    )
    cockpit = repo / '.zoo-agent' / 'cockpit' / 'index.html'
    data_path = repo / '.zoo-agent' / 'cockpit' / 'cockpit_data.json'
    digest = repo / '.zoo-agent' / 'session' / 'session_digest.md'
    assert cockpit.exists()
    assert data_path.exists()
    assert digest.exists()
    data = load(data_path)
    assert data['session']['status'] in {'active', 'paused', 'needs_attention'}
    assert data['session']['goal'] == 'prepare this project for public release'
    assert data['safety']['checkpoints_available'] is True
    html = cockpit.read_text(encoding='utf-8')
    assert 'Autopilot Session' in html
    assert 'Safety / Recovery' in html
    assert_no_internal(html)

    run([sys.executable, str(AGENT), 'stop', '--workspace', str(repo)], repo, env=env)
    stopped_data = load(data_path)
    assert stopped_data['session']['status'] == 'stopped'
    status = run([sys.executable, str(AGENT), 'status', '--workspace', str(repo), '--no-write'], repo, env=env)
    assert 'Session: status: stopped' in status.stdout
    assert_no_internal(status.stdout)
    print('session cockpit sync tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
