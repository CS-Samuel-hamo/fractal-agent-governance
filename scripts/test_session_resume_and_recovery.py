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
sys.path.insert(0, str(ROOT / 'scripts'))


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


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def init_repo(prefix: str, env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix=prefix, dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Recovery\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'recovery@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Recovery Test'], repo, env=env)
    run(['git', 'add', 'README.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def env() -> dict[str, str]:
    payload = os.environ.copy()
    payload.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='session-recovery-codex-home-')).resolve()))
    Path(payload['CODEX_HOME']).mkdir(parents=True, exist_ok=True)
    return payload


def test_stale_lock_and_missing_map(test_env: dict[str, str]) -> None:
    repo = init_repo('session-stale-lock-', test_env)
    state = {
        'session_id': 'session-stale',
        'goal': 'recover project session',
        'status': 'active',
        'created_at': '2026-06-21T00:00:00Z',
        'updated_at': '2026-06-21T00:00:00Z',
        'current_step': 1,
        'max_steps': 5,
        'completed_steps': 1,
        'failed_steps': 0,
        'resume_available': True,
        'cockpit_path': '.zoo-agent/cockpit/index.html',
    }
    write_json(repo / '.zoo-agent' / 'session' / 'session_state.json', state)
    write_json(
        repo / '.zoo-agent' / 'session' / 'session_lock.json', {'session_id': 'session-stale', 'created_monotonic': 1.0}
    )
    run(
        [sys.executable, str(ROOT / 'scripts' / 'session_resume_engine.py'), '--workspace', str(repo)],
        repo,
        env=test_env,
    )
    report = load(repo / '.zoo-agent' / 'session' / 'recovery_report.json')
    assert report['safe_to_continue'] is True
    assert report['recovery_status'] == 'recovered'
    assert (repo / '.zoo-agent' / 'map' / 'project_map.json').exists()
    assert (repo / '.zoo-agent' / 'cockpit' / 'index.html').exists()


def test_corrupted_state(test_env: dict[str, str]) -> None:
    repo = init_repo('session-corrupted-', test_env)
    path = repo / '.zoo-agent' / 'session' / 'session_state.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{not json', encoding='utf-8')
    run(
        [sys.executable, str(ROOT / 'scripts' / 'session_resume_engine.py'), '--workspace', str(repo)],
        repo,
        env=test_env,
    )
    report = load(repo / '.zoo-agent' / 'session' / 'recovery_report.json')
    assert report['recovery_status'] == 'needs_attention'
    assert report['safe_to_continue'] is False


def test_no_delivery_and_blocked_zone(test_env: dict[str, str]) -> None:
    repo = init_repo('session-nodelivery-', test_env)
    run([sys.executable, str(AGENT), 'config', 'backend', 'dry_run', '--workspace', str(repo)], repo, env=test_env)
    run([sys.executable, str(AGENT), 'start', 'prepare release docs', '--workspace', str(repo)], repo, env=test_env)
    state = load(repo / '.zoo-agent' / 'session' / 'session_state.json')
    assert state['status'] == 'needs_attention'
    assert state['attention_required'] is True

    blocked = init_repo('session-blocked-zone-', test_env)
    map_dir = blocked / '.zoo-agent' / 'map'
    evidence = [{'kind': 'test', 'path': 'README.md', 'summary': 'blocked fixture', 'confidence': 1.0}]
    write_json(
        map_dir / 'project_map.json',
        {
            'project_name': 'Blocked',
            'project_type': 'fixture',
            'main_goal': 'avoid unsafe work',
            'modules': [],
            'capabilities': [],
            'risks': [],
            'next_actions': [
                {
                    'action_id': 'blocked-action',
                    'title': 'Edit auth configuration',
                    'why_now': 'Unsafe fixture.',
                    'expected_impact': 'none',
                    'risk_level': 'low',
                    'target_files': ['.env'],
                    'autopilot_eligible': True,
                    'evidence': evidence,
                }
            ],
        },
    )
    run([sys.executable, str(AGENT), 'start', 'avoid unsafe work', '--workspace', str(blocked)], blocked, env=test_env)
    blocked_state = load(blocked / '.zoo-agent' / 'session' / 'session_state.json')
    assert blocked_state['status'] == 'needs_attention'
    assert not (blocked / '.env').exists()


def test_budget_decision() -> None:
    from session_budget_manager import budget_decision

    decision = budget_decision(
        {'current_step': 3},
        {'steps': [{'outcome': 'no_delivery'}, {'outcome': 'no_delivery'}]},
        {'max_steps': 5, 'max_no_delivery': 1},
    )
    assert decision['status'] == 'needs_attention'
    assert 'no_delivery_budget_exceeded' in decision['reasons']


def main() -> int:
    test_env = env()
    test_stale_lock_and_missing_map(test_env)
    test_corrupted_state(test_env)
    test_no_delivery_and_blocked_zone(test_env)
    test_budget_decision()
    print('session resume and recovery tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
