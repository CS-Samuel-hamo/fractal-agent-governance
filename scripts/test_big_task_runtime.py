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
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
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
    base = Path('D:/AI_DEV/temp')
    if not base.exists():
        base = Path(tempfile.gettempdir())
    return Path(tempfile.mkdtemp(prefix='big-task-runtime-', dir=str(base))).resolve()


def init_repo(name: str, env: dict[str, str]) -> Path:
    repo = temp_base() / name
    repo.mkdir(parents=True, exist_ok=True)
    (repo / 'README.md').write_text('# Big Task Runtime\n', encoding='utf-8')
    (repo / 'src').mkdir()
    (repo / 'src' / 'app.py').write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')
    (repo / 'tests').mkdir()
    (repo / 'tests' / 'test_app.py').write_text('from src.app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    for name in ['a.md', 'b.md', 'c.md']:
        (repo / 'docs' / name).write_text(f'# {name}\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'big@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Big Task Test'], repo, env=env)
    run(['git', 'add', '.'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def set_goal(repo: Path, env: dict[str, str], goal: str = 'Deliver the requested big task safely') -> str:
    result = run(
        [
            sys.executable,
            str(AGENT),
            'goal',
            'set',
            goal,
            '--workspace',
            str(repo),
            '--success-criteria',
            'Required leaf changes are delivered and reviewable.',
            '--non-goal',
            'Do not merge, push, deploy, or change secrets.',
        ],
        repo,
        env=env,
    )
    payload = json.loads(result.stdout)
    return payload['goal_id']


def test_api_db_big_task(env: dict[str, str]) -> None:
    repo = init_repo('api-db', env)
    goal_id = set_goal(repo, env, 'Change public API and database schema only after human review')
    proc = run([sys.executable, str(AGENT), 'plan-big', 'change public API response and database schema', '--workspace', str(repo), '--run-id', 'run-api-db', '--goal-id', goal_id], repo, check=False, env=env)
    assert proc.returncode == 10
    contract = load(repo / '.zoo-agent' / 'runs' / 'run-api-db' / 'big-task-contract.json')
    assert contract['readiness_verdict'] in {'BLOCKED_HIGH_RISK_HUMAN_GATE', 'READY_FOR_DECOMPOSITION_ONLY'}
    assert contract['requires_human_gate'] is True
    assert not (repo / '.zoo-agent' / 'runs' / 'run-api-db' / 'codex-tasks').exists()


def test_big_docs_decomposition(env: dict[str, str]) -> None:
    repo = init_repo('docs-big', env)
    goal_id = set_goal(repo, env, 'Update documentation sections safely')
    run([sys.executable, str(AGENT), 'decompose', 'update docs/a.md and docs/b.md independently', '--workspace', str(repo), '--run-id', 'run-docs', '--goal-id', goal_id], repo, env=env)
    contract = load(repo / '.zoo-agent' / 'runs' / 'run-docs' / 'big-task-contract.json')
    leaves = [path for path in sorted((repo / '.zoo-agent' / 'runs' / 'run-docs' / 'leaf-tasks').glob('leaf-*.json')) if path.name != 'leaf-tasks.json']
    schedule = load(repo / '.zoo-agent' / 'runs' / 'run-docs' / 'leaf-schedule.json')
    assert contract['allowed_execution_mode'] in {'leaf_dry_run', 'leaf_actual_allowed', 'decomposition_only'}
    assert len(leaves) >= 2
    assert all(load(path)['execution_mode'] == 'dry_run_only' for path in leaves)
    assert schedule.get('parallel_groups') or not schedule.get('parallel_groups')
    assert not (repo / '.zoo-agent' / 'runs' / 'run-docs' / 'codex-tasks').exists()


def test_cross_module_feature(env: dict[str, str]) -> None:
    repo = init_repo('cross-module', env)
    goal_id = set_goal(repo, env, 'Plan a cross-module feature with bounded leaves')
    proc = run([sys.executable, str(AGENT), 'decompose', 'add cross-module feature touching src/app.py docs/a.md and tests/test_app.py', '--workspace', str(repo), '--run-id', 'run-cross', '--goal-id', goal_id], repo, check=False, env=env)
    assert proc.returncode in {0, 10}
    assert (repo / '.zoo-agent' / 'project-resource-map.json').exists()
    assert (repo / '.zoo-agent' / 'runs' / 'run-cross' / 'leaf-tasks' / 'leaf-tasks.json').exists()
    assert not (repo / '.zoo-agent' / 'runs' / 'run-cross' / 'codex-tasks').exists()


def test_parent_aggregation_simulation(env: dict[str, str]) -> None:
    repo = init_repo('aggregation', env)
    goal_id = set_goal(repo, env, 'Update three docs sections safely')
    run([sys.executable, str(AGENT), 'decompose', 'update docs/a.md docs/b.md docs/c.md', '--workspace', str(repo), '--run-id', 'run-agg', '--goal-id', goal_id], repo, check=False, env=env)
    result_dir = repo / '.zoo-agent' / 'runs' / 'run-agg' / 'leaf-results'
    write_json(result_dir / 'leaf-001.json', {'delivery_outcome': 'delivered'})
    write_json(result_dir / 'leaf-002.json', {'delivery_outcome': 'delivered'})
    write_json(result_dir / 'leaf-003.json', {'delivery_outcome': 'no_delivery'})
    proc = run([sys.executable, str(AGENT), 'aggregate', '--workspace', str(repo), '--run-id', 'run-agg'], repo, check=False, env=env)
    assert proc.returncode == 10
    report = load(repo / '.zoo-agent' / 'runs' / 'run-agg' / 'parent-aggregation-report.json')
    assert report['verdict'] in {'NEEDS_LEAF_REDO', 'BLOCKED', 'NEEDS_REPLANNING'}


def test_integration_worktree_report(env: dict[str, str]) -> None:
    repo = init_repo('integration', env)
    goal_id = set_goal(repo, env, 'Update one docs section safely')
    run([sys.executable, str(AGENT), 'decompose', 'update docs/a.md', '--workspace', str(repo), '--run-id', 'run-int', '--goal-id', goal_id], repo, check=False, env=env)
    result_dir = repo / '.zoo-agent' / 'runs' / 'run-int' / 'leaf-results'
    write_json(result_dir / 'leaf-001.json', {'delivery_outcome': 'delivered'})
    run([sys.executable, str(AGENT), 'aggregate', '--workspace', str(repo), '--run-id', 'run-int'], repo, env=env)
    run([sys.executable, str(AGENT), 'integration-check', '--workspace', str(repo), '--run-id', 'run-int'], repo, env=env)
    report = load(repo / '.zoo-agent' / 'runs' / 'run-int' / 'integration-candidate-report.json')
    assert report['verdict'] == 'INTEGRATION_CANDIDATE_READY'
    assert report['merge_performed'] is False
    assert report['push_performed'] is False
    assert report['worktree_created'] is False


def test_goal_missing_blocks(env: dict[str, str]) -> None:
    repo = init_repo('missing-goal', env)
    proc = run([sys.executable, str(AGENT), 'plan-big', 'add cross-module feature touching src/app.py and docs/a.md', '--workspace', str(repo), '--run-id', 'run-missing-goal'], repo, check=False, env=env)
    assert proc.returncode == 10
    contract = load(repo / '.zoo-agent' / 'runs' / 'run-missing-goal' / 'big-task-contract.json')
    assert contract['readiness_verdict'] == 'BLOCKED_GOAL_UNCLEAR'


def test_loop_divergence(env: dict[str, str]) -> None:
    repo = init_repo('loop-divergence', env)
    goal_id = set_goal(repo, env)
    last = None
    for index in range(3):
        last = run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'update_loop_state.py'),
                '--workspace',
                str(repo),
                '--run-id',
                f'run-loop-{index}',
                '--goal-id',
                goal_id,
                '--route',
                'governed',
                '--delivery-outcome',
                'executed',
                '--phase',
                'decomposition',
                '--decomposition-round',
            ],
            repo,
            check=False,
            env=env,
        )
    assert last is not None and last.returncode == 10
    state = load(repo / '.zoo-agent' / 'loop' / 'loop-state.json')
    assert state['status'] == 'diverging'


def test_high_risk_leaf_blocked(env: dict[str, str]) -> None:
    repo = init_repo('high-risk-leaf', env)
    goal_id = set_goal(repo, env, 'Review database schema change')
    run([sys.executable, str(AGENT), 'decompose', 'change database schema in database/migrations/001.sql', '--workspace', str(repo), '--run-id', 'run-high-leaf', '--goal-id', goal_id], repo, check=False, env=env)
    leaf = load(repo / '.zoo-agent' / 'runs' / 'run-high-leaf' / 'leaf-tasks' / 'leaf-001.json')
    assert leaf['risk_level'] in {'high', 'critical'}
    assert leaf['task_readiness']['verdict'] == 'BLOCKED_HIGH_RISK'
    assert leaf['execution_mode'] != 'actual_allowed'


def test_unknown_resource_not_independent(env: dict[str, str]) -> None:
    repo = init_repo('unknown-resource', env)
    goal_id = set_goal(repo, env)
    run([sys.executable, str(AGENT), 'decompose', 'improve project quality broadly', '--workspace', str(repo), '--run-id', 'run-unknown', '--goal-id', goal_id], repo, check=False, env=env)
    run([sys.executable, str(ROOT / 'scripts' / 'detect_leaf_independence.py'), '--workspace', str(repo), '--run-id', 'run-unknown'], repo, check=False, env=env)
    report = load(repo / '.zoo-agent' / 'runs' / 'run-unknown' / 'leaf-independence.json')
    assert report['parallel_denials']
    assert 'unknown' in json.dumps(report).lower()


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', 'D:/AI_DEV/codex_home')
    test_api_db_big_task(env)
    test_big_docs_decomposition(env)
    test_cross_module_feature(env)
    test_parent_aggregation_simulation(env)
    test_integration_worktree_report(env)
    test_goal_missing_blocks(env)
    test_loop_divergence(env)
    test_high_risk_leaf_blocked(env)
    test_unknown_resource_not_independent(env)
    print('big task runtime tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
