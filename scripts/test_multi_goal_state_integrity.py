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
    return Path(tempfile.mkdtemp(prefix='multi-goal-state-integrity-', dir=str(base))).resolve()


def init_repo(name: str) -> Path:
    repo = temp_base() / name
    repo.mkdir(parents=True, exist_ok=True)
    (repo / 'README.md').write_text('# Multi Goal State Integrity\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'a.md').write_text('# A\n', encoding='utf-8')
    (repo / 'docs' / 'b.md').write_text('# B\n', encoding='utf-8')
    (repo / 'src').mkdir()
    (repo / 'src' / 'api.py').write_text('def route():\n    return {}\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'state-integrity@example.local'], repo)
    run(['git', 'config', 'user.name', 'State Integrity Test'], repo)
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


def state(repo: Path) -> dict:
    return load(repo / '.zoo-agent' / 'goal' / 'goal_state.json')


def by_id(payload: dict, goal_id: str) -> dict:
    return next(item for item in payload['goals'] if item['goal_id'] == goal_id)


def assert_sticky_preserved(before: dict, after: dict, goal_id: str) -> None:
    old = by_id(before, goal_id)
    new = by_id(after, goal_id)
    for field in ['priority', 'status', 'resource_usage', 'depends_on', 'blocks', 'created_at']:
        assert new.get(field) == old.get(field), f'{goal_id}.{field} changed: {old.get(field)} -> {new.get(field)}'


def setup_goals(repo: Path) -> None:
    set_goal(repo, 'goal-a', 'Add diagnostics docs outline', priority=80, resource='diagnostics-report')
    set_goal(
        repo,
        'goal-b',
        'Update diagnostics report output format docs',
        priority=70,
        resource='diagnostics-report',
        no_activate=True,
    )
    set_goal(
        repo,
        'goal-c',
        'Change public API response and database schema',
        priority=90,
        resource='api_contract:*',
        no_activate=True,
    )
    set_goal(repo, 'goal-d', 'Improve README onboarding wording', priority=20, resource='README.md', no_activate=True)
    run([sys.executable, str(AGENT), 'goal', 'block', '--workspace', str(repo), '--goal-id', 'goal-c'], repo)
    run([sys.executable, str(AGENT), 'goal', 'backlog', '--workspace', str(repo), '--goal-id', 'goal-d'], repo)
    run([sys.executable, str(AGENT), 'goal', 'resume', '--workspace', str(repo), '--goal-id', 'goal-a'], repo)


def run_active_aggregation(repo: Path) -> None:
    run_id = 'run-integrity'
    run(
        [
            sys.executable,
            str(AGENT),
            'decompose',
            'Add diagnostics docs outline',
            '--workspace',
            str(repo),
            '--run-id',
            run_id,
            '--goal-id',
            'goal-a',
        ],
        repo,
        check=False,
    )
    run(
        [sys.executable, str(AGENT), 'aggregate', '--workspace', str(repo), '--run-id', run_id, '--goal-id', 'goal-a'],
        repo,
        check=False,
    )


def test_071_pollution_regression() -> None:
    repo = init_repo('pollution-regression')
    setup_goals(repo)
    before = state(repo)
    before_path = repo / '.zoo-agent' / 'goal' / 'before-aggregation-goal-state.json'
    write_json(before_path, before)
    run_active_aggregation(repo)
    after = state(repo)

    assert by_id(after, 'goal-a')['priority'] == 80
    assert by_id(after, 'goal-b')['priority'] == 70
    assert by_id(after, 'goal-c')['priority'] == 90
    assert by_id(after, 'goal-d')['priority'] == 20
    assert by_id(after, 'goal-c')['status'] == 'blocked'
    assert by_id(after, 'goal-d')['status'] == 'backlog'
    assert by_id(after, 'goal-a')['resource_usage'] == ['diagnostics-report']
    assert by_id(after, 'goal-b')['resource_usage'] == ['diagnostics-report']
    assert_sticky_preserved(before, after, 'goal-b')
    assert_sticky_preserved(before, after, 'goal-c')
    assert_sticky_preserved(before, after, 'goal-d')
    proc = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'check_goal_state_invariants.py'),
            '--workspace',
            str(repo),
            '--before',
            str(before_path),
        ],
        repo,
    )
    assert json.loads(proc.stdout)['status'] == 'pass'


def test_patch_revision_and_illegal_transitions() -> None:
    repo = init_repo('patch-rules')
    setup_goals(repo)
    current = state(repo)
    stale_patch = {
        'patch_id': 'stale',
        'created_at': '2026-01-01T00:00:00Z',
        'source': 'test',
        'reason': 'stale patch',
        'base_revision': int(current.get('revision') or 0) + 99,
        'changes': [{'goal_id': 'goal-a', 'op': 'set_progress', 'to': 10, 'reason': 'stale'}],
    }
    stale_path = repo / '.zoo-agent' / 'goal' / 'stale-patch.json'
    write_json(stale_path, stale_patch)
    proc = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'apply_goal_state_patch.py'),
            '--workspace',
            str(repo),
            '--patch',
            str(stale_path),
        ],
        repo,
        check=False,
    )
    assert proc.returncode == 10

    illegal_patch = {
        'patch_id': 'illegal',
        'created_at': '2026-01-01T00:00:00Z',
        'source': 'test',
        'reason': '',
        'base_revision': int(state(repo).get('revision') or 0),
        'changes': [{'goal_id': 'goal-c', 'op': 'set_status', 'from': 'blocked', 'to': 'paused'}],
    }
    illegal_path = repo / '.zoo-agent' / 'goal' / 'illegal-patch.json'
    write_json(illegal_path, illegal_patch)
    proc2 = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'apply_goal_state_patch.py'),
            '--workspace',
            str(repo),
            '--patch',
            str(illegal_path),
        ],
        repo,
        check=False,
    )
    assert proc2.returncode == 10
    assert by_id(state(repo), 'goal-c')['status'] == 'blocked'


def test_legal_patch_transitions() -> None:
    repo = init_repo('legal-patches')
    setup_goals(repo)
    current = state(repo)
    patch = {
        'patch_id': 'complete-active',
        'created_at': '2026-01-01T00:00:00Z',
        'source': 'aggregation',
        'reason': 'aggregation completed active goal',
        'base_revision': int(current.get('revision') or 0),
        'changes': [
            {
                'goal_id': 'goal-a',
                'op': 'set_completion',
                'from': 'active',
                'to': 'completed',
                'reason': 'aggregation completed active goal',
            }
        ],
    }
    path = repo / '.zoo-agent' / 'goal' / 'complete-patch.json'
    write_json(path, patch)
    run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'apply_goal_state_patch.py'),
            '--workspace',
            str(repo),
            '--patch',
            str(path),
        ],
        repo,
    )
    assert by_id(state(repo), 'goal-a')['status'] == 'completed'

    current = state(repo)
    patch2 = {
        'patch_id': 'resume-paused',
        'created_at': '2026-01-01T00:00:00Z',
        'source': 'scheduler',
        'reason': 'scheduler selected next goal',
        'base_revision': int(current.get('revision') or 0),
        'changes': [
            {
                'goal_id': 'goal-b',
                'op': 'set_status',
                'from': 'paused',
                'to': 'active',
                'reason': 'scheduler selected next goal',
            }
        ],
    }
    path2 = repo / '.zoo-agent' / 'goal' / 'resume-patch.json'
    write_json(path2, patch2)
    run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'apply_goal_state_patch.py'),
            '--workspace',
            str(repo),
            '--patch',
            str(path2),
        ],
        repo,
    )
    assert state(repo)['global_loop_state']['active_goal_id'] == 'goal-b'
    assert by_id(state(repo), 'goal-b')['status'] == 'active'


def main() -> int:
    os.environ.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='agent-runtime-codex-home-')).resolve()))
    test_071_pollution_regression()
    test_patch_revision_and_illegal_transitions()
    test_legal_patch_transitions()
    print('multi goal state integrity tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
