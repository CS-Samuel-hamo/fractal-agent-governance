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
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def init_repo(prefix: str, env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix=prefix, dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Session Runtime\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'session@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Session Test'], repo, env=env)
    run(['git', 'add', 'README.md', 'docs/guide.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def env() -> dict[str, str]:
    payload = os.environ.copy()
    payload.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='session-codex-home-')).resolve()))
    Path(payload['CODEX_HOME']).mkdir(parents=True, exist_ok=True)
    return payload


def assert_no_internal(text: str) -> None:
    lowered = text.lower()
    for term in ['eval', 'governance', 'planner', 'verifier', 'scheduler', 'backend internals']:
        assert term not in lowered, f'internal term leaked: {term}'


def main() -> int:
    test_env = env()
    repo = init_repo('long-session-', test_env)
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo, env=test_env)

    start = run(
        [sys.executable, str(AGENT), 'start', 'prepare this project for public release', '--workspace', str(repo)],
        repo,
        env=test_env,
    )
    assert 'Done.' in start.stdout or 'Needs attention.' in start.stdout
    assert_no_internal(start.stdout)
    state_path = repo / '.zoo-agent' / 'session' / 'session_state.json'
    digest_path = repo / '.zoo-agent' / 'session' / 'session_digest.md'
    cockpit_path = repo / '.zoo-agent' / 'cockpit' / 'index.html'
    assert state_path.exists()
    assert digest_path.exists()
    assert cockpit_path.exists()
    state = load(state_path)
    assert state['goal'] == 'prepare this project for public release'
    assert state['status'] in {'active', 'paused', 'needs_attention'}
    assert state['current_step'] >= 1
    selected = load(repo / '.zoo-agent' / 'autopilot' / 'selected_next_action.json')
    assert selected['source'] == 'project_map.next_actions'
    checkpoints = load(repo / '.zoo-agent' / 'autopilot' / 'checkpoints.json')
    assert checkpoints['checkpoints']
    history = load(repo / '.zoo-agent' / 'session' / 'session_history.json')
    assert len(history['steps']) == 1

    cont = run([sys.executable, str(AGENT), 'continue', '--workspace', str(repo)], repo, env=test_env)
    assert_no_internal(cont.stdout)
    history_after = load(repo / '.zoo-agent' / 'session' / 'session_history.json')
    assert len(history_after['steps']) >= 2
    checkpoints_after = load(repo / '.zoo-agent' / 'autopilot' / 'checkpoints.json')
    assert len(checkpoints_after['checkpoints']) >= 2

    status = run([sys.executable, str(AGENT), 'status', '--workspace', str(repo), '--no-write'], repo, env=test_env)
    assert '"mode": "status"' in status.stdout
    assert 'Session: status:' in status.stdout
    assert '.zoo-agent/session/session_digest.md' in status.stdout
    assert '.zoo-agent/cockpit/index.html' in status.stdout
    assert_no_internal(status.stdout)

    undo = run([sys.executable, str(AGENT), 'undo', '--workspace', str(repo)], repo, env=test_env)
    assert 'checkpoint available' in undo.stdout
    assert (repo / '.zoo-agent' / 'cockpit' / 'cockpit_data.json').exists()
    digest_text = digest_path.read_text(encoding='utf-8')
    assert 'Session Goal' in digest_text
    assert 'Suggested Commands' in digest_text
    assert_no_internal(digest_text)

    before_stop_steps = len(load(repo / '.zoo-agent' / 'session' / 'session_history.json')['steps'])
    stop = run([sys.executable, str(AGENT), 'stop', '--workspace', str(repo)], repo, env=test_env)
    assert 'stopped' in stop.stdout
    stopped = load(state_path)
    assert stopped['status'] == 'stopped'
    run([sys.executable, str(AGENT), 'continue', '--workspace', str(repo)], repo, env=test_env)
    after_stop_steps = len(load(repo / '.zoo-agent' / 'session' / 'session_history.json')['steps'])
    assert after_stop_steps == before_stop_steps
    print('long running session runtime tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
