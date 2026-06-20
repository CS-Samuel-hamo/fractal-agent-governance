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


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if check and proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def repo() -> Path:
    base = Path(tempfile.gettempdir())
    path = Path(tempfile.mkdtemp(prefix='scheduler-filtering-', dir=str(base))).resolve()
    (path / 'README.md').write_text('# Scheduler Filtering\n', encoding='utf-8')
    run(['git', 'init'], path)
    run(['git', 'config', 'user.email', 'scheduler@example.local'], path)
    run(['git', 'config', 'user.name', 'Scheduler Filtering Test'], path)
    run(['git', 'add', '.'], path)
    run(['git', 'commit', '-m', 'init'], path)
    (path / '.zoo-agent').mkdir()
    (path / '.zoo-agent' / 'bootstrap.lock').write_text('test\n', encoding='utf-8')
    return path


def set_goal(path: Path, goal_id: str, text: str, priority: int, *, resource: str, no_activate: bool = False) -> None:
    cmd = [
        sys.executable,
        str(AGENT),
        'goal',
        'set',
        text,
        '--workspace',
        str(path),
        '--goal-id',
        goal_id,
        '--priority',
        str(priority),
        '--resource',
        resource,
        '--success-criteria',
        f'{goal_id} criteria',
        '--non-goal',
        'Do not merge or push.',
    ]
    if no_activate:
        cmd.append('--no-activate')
    run(cmd, path)


def test_bootstrap_runtime_goal_does_not_block_production_goal() -> None:
    path = repo()
    set_goal(path, 'runtime-maintenance', 'Operate this project through the CLI-first AI Agent Runtime with bounded Codex execution.', 100, resource='runtime:*')
    set_goal(path, 'production-low', 'Improve README onboarding wording for real users.', 10, resource='README.md', no_activate=True)
    run([sys.executable, str(AGENT), 'goal', 'schedule', '--workspace', str(path)], path)
    schedule = load(path / '.zoo-agent' / 'goal' / 'goal-schedule.json')
    assert schedule['active_goal_id'] == 'production-low'
    assert schedule['eligible_goals'][0]['goal_id'] == 'production-low'
    assert schedule['excluded_goals'][0]['goal_id'] == 'runtime-maintenance'
    assert schedule['exclusion_reason']['runtime-maintenance'] == 'excluded_system_goal'
    assert all(item['goal_id'] != 'runtime-maintenance' for item in schedule['ranking'] if item['goal_id'] in {row['goal_id'] for row in schedule['eligible_goals']})


def test_only_production_goals_affect_convergence() -> None:
    path = repo()
    set_goal(path, 'runtime-maintenance', 'Runtime maintenance health metrics goal', 100, resource='runtime:*')
    set_goal(path, 'production-a', 'Improve README onboarding wording for real users.', 50, resource='README.md', no_activate=True)
    run([sys.executable, str(AGENT), 'goal', 'complete', '--workspace', str(path), '--goal-id', 'production-a'], path)
    run([sys.executable, str(AGENT), 'global-loop', '--workspace', str(path), '--no-advance'], path)
    loop = load(path / '.zoo-agent' / 'goal' / 'global-loop-state.json')
    assert loop['system_status'] == 'converged'
    assert 'runtime-maintenance' not in loop['completed_goals']


def main() -> int:
    os.environ.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='agent-runtime-codex-home-')).resolve()))
    test_bootstrap_runtime_goal_does_not_block_production_goal()
    test_only_production_goals_affect_convergence()
    print('scheduler filtering tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
