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


def run(cmd: list[str], cwd: Path, *, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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
    return json.loads(path.read_text(encoding='utf-8'))


def init_repo(env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix='goal-loop-runtime-')).resolve()
    (repo / 'README.md').write_text('# Goal Loop\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'loop@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Loop Test'], repo, env=env)
    run(['git', 'add', 'README.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def test_goal_cli(repo: Path, env: dict[str, str]) -> str:
    run(
        [
            sys.executable,
            str(AGENT),
            'goal',
            'set',
            'Ship bounded README fixes',
            '--workspace',
            str(repo),
            '--success-criteria',
            'README updated safely',
            '--non-goal',
            'No release',
            '--risk-tolerance',
            'low',
        ],
        repo,
        env=env,
    )
    current = load(repo / '.zoo-agent' / 'goal' / 'current-goal.json')
    assert current['goal'] == 'Ship bounded README fixes'
    assert current['active'] is True
    assert current['risk_tolerance'] == 'low'
    assert (repo / '.zoo-agent' / 'goals' / f"{current['goal_id']}.json").exists()
    show = run([sys.executable, str(AGENT), 'goal', 'show', '--workspace', str(repo)], repo, env=env)
    assert 'Ship bounded README fixes' in show.stdout
    return current['goal_id']


def test_loop_cli(repo: Path, env: dict[str, str]) -> None:
    run([sys.executable, str(AGENT), 'loop', 'reset', '--workspace', str(repo), '--max-iterations', '3'], repo, env=env)
    state = load(repo / '.zoo-agent' / 'loop' / 'loop-state.json')
    assert state['iteration'] == 0
    assert state['max_iterations'] == 3
    run([sys.executable, str(AGENT), 'loop', 'set', '--workspace', str(repo), '--max-iterations', '2'], repo, env=env)
    state = load(repo / '.zoo-agent' / 'loop' / 'loop-state.json')
    assert state['max_iterations'] == 2
    run([sys.executable, str(AGENT), 'loop', 'status', '--workspace', str(repo)], repo, env=env)
    run([sys.executable, str(AGENT), 'loop', 'explain', '--workspace', str(repo)], repo, check=False, env=env)


def test_loop_loss_controls(repo: Path, env: dict[str, str], goal_id: str) -> None:
    update = ROOT / 'scripts' / 'update_loop_state.py'
    run([sys.executable, str(AGENT), 'loop', 'reset', '--workspace', str(repo), '--max-iterations', '5'], repo, env=env)
    run([sys.executable, str(update), '--workspace', str(repo), '--run-id', 'run-delivered', '--goal-id', goal_id, '--route', 'fast', '--delivery-outcome', 'delivered'], ROOT, check=False, env=env)
    state = load(repo / '.zoo-agent' / 'loop' / 'loop-state.json')
    assert state['status'] == 'converged'

    run([sys.executable, str(AGENT), 'loop', 'reset', '--workspace', str(repo), '--max-iterations', '5'], repo, env=env)
    for idx in [1, 2]:
        run([sys.executable, str(update), '--workspace', str(repo), '--run-id', f'run-no-delivery-{idx}', '--goal-id', goal_id, '--route', 'fast', '--delivery-outcome', 'no_delivery'], ROOT, check=False, env=env)
    state = load(repo / '.zoo-agent' / 'loop' / 'loop-state.json')
    assert state['status'] == 'stopped'
    assert state['next_action'] == 'clarify_task_before_actual_run'

    run([sys.executable, str(AGENT), 'loop', 'reset', '--workspace', str(repo), '--max-iterations', '5'], repo, env=env)
    for idx in [1, 2]:
        run([sys.executable, str(update), '--workspace', str(repo), '--run-id', f'run-backend-{idx}', '--goal-id', goal_id, '--route', 'fast', '--delivery-outcome', 'blocked', '--failure-type', 'timeout'], ROOT, check=False, env=env)
    state = load(repo / '.zoo-agent' / 'loop' / 'loop-state.json')
    assert state['status'] == 'stopped'
    assert state['next_action'] == 'switch_to_dry_run_or_manual_task_pack'

    run([sys.executable, str(AGENT), 'loop', 'reset', '--workspace', str(repo), '--max-iterations', '5'], repo, env=env)
    for idx in [1, 2]:
        run([sys.executable, str(update), '--workspace', str(repo), '--run-id', f'run-doc-{idx}', '--goal-id', goal_id, '--route', 'fast', '--delivery-outcome', 'executed', '--doc-only'], ROOT, check=False, env=env)
    state = load(repo / '.zoo-agent' / 'loop' / 'loop-state.json')
    assert state['status'] == 'blocked'
    assert state['next_action'] == 'schedule_implementation_pass'

    run([sys.executable, str(AGENT), 'loop', 'reset', '--workspace', str(repo), '--max-iterations', '5'], repo, env=env)
    for idx in [1, 2]:
        run([sys.executable, str(update), '--workspace', str(repo), '--run-id', f'run-local-{idx}', '--goal-id', goal_id, '--route', 'fast', '--delivery-outcome', 'executed', '--local-optimization'], ROOT, check=False, env=env)
    state = load(repo / '.zoo-agent' / 'loop' / 'loop-state.json')
    assert state['status'] == 'converged'
    assert state['next_action'] == 'record_follow_up'


def test_transient_goal(repo: Path, env: dict[str, str]) -> None:
    run(
        [
            sys.executable,
            str(AGENT),
            'run',
            '--workspace',
            str(repo),
            '--run-id',
            'run-transient',
            '--task-id',
            'task-transient',
            '--dry-run',
            'fix README typo',
        ],
        repo,
        env=env,
    )
    report = load(repo / '.zoo-agent' / 'runs' / 'run-transient' / 'cli-runtime' / 'task-transient.json')
    assert report['goal_id']
    assert report['goal_alignment']['status'] in {'pass', 'needs_review'}


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='codex-home-loop-')).resolve()))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)
    repo = init_repo(env)
    goal_id = test_goal_cli(repo, env)
    test_loop_cli(repo, env)
    test_loop_loss_controls(repo, env, goal_id)
    run([sys.executable, str(AGENT), 'goal', 'clear', '--workspace', str(repo)], repo, env=env)
    test_transient_goal(repo, env)
    print('goal loop runtime tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
