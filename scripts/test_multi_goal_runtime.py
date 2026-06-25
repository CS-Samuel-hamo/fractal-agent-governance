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
    proc = subprocess.run(
        cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if check and proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def temp_base() -> Path:
    base = Path(tempfile.gettempdir())
    if not base.exists():
        base = Path(tempfile.gettempdir())
    return Path(tempfile.mkdtemp(prefix='multi-goal-runtime-', dir=str(base))).resolve()


def init_repo(name: str) -> Path:
    repo = temp_base() / name
    repo.mkdir(parents=True, exist_ok=True)
    (repo / 'README.md').write_text('# Multi Goal Runtime\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'a.md').write_text('# A\n', encoding='utf-8')
    (repo / 'docs' / 'b.md').write_text('# B\n', encoding='utf-8')
    (repo / 'src').mkdir()
    (repo / 'src' / 'api.py').write_text('def route():\n    return {}\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'multi-goal@example.local'], repo)
    run(['git', 'config', 'user.name', 'Multi Goal Test'], repo)
    run(['git', 'add', '.'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    marker = repo / '.zoo-agent'
    marker.mkdir()
    (marker / 'bootstrap.lock').write_text('test bootstrap marker\n', encoding='utf-8')
    return repo


def set_goal(repo: Path, goal_id: str, text: str, *, priority: int, resource: str, no_activate: bool = False) -> None:
    cmd = [
        sys.executable,
        str(AGENT),
        'goal',
        'set',
        text,
        '--workspace',
        str(repo),
        '--goal-id',
        goal_id,
        '--priority',
        str(priority),
        '--resource',
        resource,
        '--success-criteria',
        f'{goal_id} is reviewable.',
        '--non-goal',
        'Do not merge or push.',
    ]
    if no_activate:
        cmd.append('--no-activate')
    run(cmd, repo)


def goal_state(repo: Path) -> dict:
    return load(repo / '.zoo-agent' / 'goal' / 'goal_state.json')


def goal_by_id(repo: Path, goal_id: str) -> dict:
    state = goal_state(repo)
    return next(item for item in state['goals'] if item['goal_id'] == goal_id)


def test_multiple_goals_scheduling() -> None:
    repo = init_repo('scheduling')
    set_goal(repo, 'goal-a', 'Update docs/a.md', priority=90, resource='docs/a.md')
    set_goal(repo, 'goal-b', 'Update docs/b.md', priority=40, resource='docs/b.md', no_activate=True)
    set_goal(repo, 'goal-c', 'Backlog README cleanup', priority=10, resource='README.md', no_activate=True)
    run([sys.executable, str(AGENT), 'goal', 'backlog', '--workspace', str(repo), '--goal-id', 'goal-c'], repo)
    run([sys.executable, str(AGENT), 'goal', 'schedule', '--workspace', str(repo)], repo)
    state = goal_state(repo)
    assert state['global_loop_state']['active_goal_id'] == 'goal-a'
    assert goal_by_id(repo, 'goal-b')['status'] == 'paused'
    assert goal_by_id(repo, 'goal-c')['status'] == 'backlog'


def test_conflict_detection_pauses_lower_priority_api_goal() -> None:
    repo = init_repo('conflict')
    set_goal(repo, 'goal-api-a', 'Change public API response for A', priority=80, resource='api_contract:*')
    set_goal(
        repo, 'goal-api-b', 'Change public API response for B', priority=20, resource='api_contract:*', no_activate=True
    )
    proc = run(
        [sys.executable, str(ROOT / 'scripts' / 'goal_conflict_detector.py'), '--workspace', str(repo), '--apply'],
        repo,
        check=False,
    )
    assert proc.returncode == 10
    report = load(repo / '.zoo-agent' / 'goal' / 'goal-conflicts.json')
    assert report['conflicts']
    assert report['conflicts'][0]['severity'] == 'critical'
    assert goal_by_id(repo, 'goal-api-b')['status'] == 'paused'


def test_resource_collision_not_concurrent() -> None:
    repo = init_repo('resource-collision')
    set_goal(repo, 'goal-doc-a', 'Edit docs/a.md first', priority=70, resource='docs/a.md')
    set_goal(repo, 'goal-doc-b', 'Edit docs/a.md second', priority=65, resource='docs/a.md', no_activate=True)
    run([sys.executable, str(AGENT), 'goal', 'schedule', '--workspace', str(repo)], repo)
    state = goal_state(repo)
    active = [item for item in state['goals'] if item['status'] == 'active']
    assert len(active) == 1
    conflicts = load(repo / '.zoo-agent' / 'goal' / 'goal-conflicts.json')
    assert conflicts['conflicts']


def test_goal_switching_after_completion() -> None:
    repo = init_repo('switching')
    set_goal(repo, 'goal-a', 'Update docs/a.md', priority=90, resource='docs/a.md')
    set_goal(repo, 'goal-b', 'Update docs/b.md', priority=70, resource='docs/b.md', no_activate=True)
    run([sys.executable, str(AGENT), 'goal', 'complete', '--workspace', str(repo), '--goal-id', 'goal-a'], repo)
    run([sys.executable, str(AGENT), 'goal', 'schedule', '--workspace', str(repo)], repo)
    assert goal_state(repo)['global_loop_state']['active_goal_id'] == 'goal-b'


def test_backend_unhealthy_freezes_actual_execution() -> None:
    repo = init_repo('backend-unhealthy')
    set_goal(repo, 'goal-a', 'Update docs/a.md', priority=90, resource='docs/a.md')
    proc = run(
        [sys.executable, str(AGENT), 'global-loop', '--workspace', str(repo), '--backend-health', 'unhealthy'], repo
    )
    report = json.loads(proc.stdout)
    assert report['actual_execution_frozen'] is True
    assert report['system_status'] == 'degraded'
    assert goal_state(repo)['global_loop_state']['active_goal_id'] == ''


def test_starvation_prevention_rotates_low_priority_goal() -> None:
    repo = init_repo('starvation')
    set_goal(repo, 'goal-high', 'High priority docs/a.md', priority=90, resource='docs/a.md')
    set_goal(repo, 'goal-low', 'Low priority docs/b.md', priority=20, resource='docs/b.md', no_activate=True)
    state = goal_state(repo)
    for item in state['goals']:
        if item['goal_id'] == 'goal-high':
            item['status'] = 'active'
            item['continuous_iterations'] = 1
        if item['goal_id'] == 'goal-low':
            item['status'] = 'paused'
            item['starvation_count'] = 10
    write_json(repo / '.zoo-agent' / 'goal' / 'goal_state.json', state)
    write_json(repo / '.zoo-agent' / 'goal_state.json', state)
    run(
        [sys.executable, str(AGENT), 'goal', 'schedule', '--workspace', str(repo), '--max-continuous-iterations', '1'],
        repo,
    )
    assert goal_state(repo)['global_loop_state']['active_goal_id'] == 'goal-low'


def test_global_loop_converges_or_stops() -> None:
    repo = init_repo('convergence')
    set_goal(repo, 'goal-a', 'Update docs/a.md', priority=90, resource='docs/a.md')
    set_goal(repo, 'goal-b', 'Update docs/b.md', priority=80, resource='docs/b.md', no_activate=True)
    run([sys.executable, str(AGENT), 'goal', 'complete', '--workspace', str(repo), '--goal-id', 'goal-a'], repo)
    run([sys.executable, str(AGENT), 'goal', 'complete', '--workspace', str(repo), '--goal-id', 'goal-b'], repo)
    proc = run([sys.executable, str(AGENT), 'global-loop', '--workspace', str(repo), '--max-iterations', '10'], repo)
    report = json.loads(proc.stdout)
    assert report['system_status'] == 'converged'
    assert report['completed_goals'] == ['goal-a', 'goal-b']

    repo2 = init_repo('max-loop')
    set_goal(repo2, 'goal-a', 'Update docs/a.md', priority=90, resource='docs/a.md')
    proc2 = run([sys.executable, str(AGENT), 'global-loop', '--workspace', str(repo2), '--max-iterations', '1'], repo2)
    report2 = json.loads(proc2.stdout)
    assert report2['system_status'] in {'paused', 'active'}
    if report2['global_iteration'] >= 1:
        assert report2['global_iteration'] == 1


def main() -> int:
    os.environ.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='agent-runtime-codex-home-')).resolve()))
    test_multiple_goals_scheduling()
    test_conflict_detection_pauses_lower_priority_api_goal()
    test_resource_collision_not_concurrent()
    test_goal_switching_after_completion()
    test_backend_unhealthy_freezes_actual_execution()
    test_starvation_prevention_rotates_low_priority_goal()
    test_global_loop_converges_or_stops()
    print('multi goal runtime tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
