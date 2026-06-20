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


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def temp_base() -> Path:
    base = Path('D:/AI_DEV/temp')
    if not base.exists():
        base = Path(tempfile.gettempdir())
    return Path(tempfile.mkdtemp(prefix='goal-loop-orchestrator-', dir=str(base))).resolve()


def init_repo(name: str) -> Path:
    repo = temp_base() / name
    repo.mkdir(parents=True, exist_ok=True)
    (repo / 'README.md').write_text('# Goal Loop Test\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'a.md').write_text('# A\n', encoding='utf-8')
    (repo / 'docs' / 'b.md').write_text('# B\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'goal-loop@example.local'], repo)
    run(['git', 'config', 'user.name', 'Goal Loop Test'], repo)
    run(['git', 'add', '.'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    marker = repo / '.zoo-agent'
    marker.mkdir()
    (marker / 'bootstrap.lock').write_text('test bootstrap marker\n', encoding='utf-8')
    return repo


def set_docs_goal(repo: Path, *, two_criteria: bool = True) -> str:
    cmd = [
        sys.executable,
        str(AGENT),
        'goal',
        'set',
        'Update documentation sections safely through the goal loop',
        '--workspace',
        str(repo),
        '--success-criteria',
        'docs/a.md is delivered and reviewable.',
        '--non-goal',
        'Do not merge or push.',
    ]
    if two_criteria:
        cmd.extend(['--success-criteria', 'docs/b.md is delivered and reviewable.'])
    proc = run(cmd, repo)
    return json.loads(proc.stdout)['goal_id']


def decompose(repo: Path, run_id: str, goal_id: str, task: str) -> None:
    run([sys.executable, str(AGENT), 'decompose', task, '--workspace', str(repo), '--run-id', run_id, '--goal-id', goal_id], repo, check=False)


def test_completed_goal_loop() -> None:
    repo = init_repo('completed')
    goal_id = set_docs_goal(repo)
    decompose(repo, 'run-complete', goal_id, 'update docs/a.md docs/b.md')
    result_dir = repo / '.zoo-agent' / 'runs' / 'run-complete' / 'leaf-results'
    write_json(result_dir / 'leaf-001.json', {'delivery_outcome': 'delivered'})
    write_json(result_dir / 'leaf-002.json', {'delivery_outcome': 'delivered'})
    run([sys.executable, str(AGENT), 'aggregate', '--workspace', str(repo), '--run-id', 'run-complete', '--goal-id', goal_id], repo)
    matrix = load(repo / '.zoo-agent' / 'runs' / 'run-complete' / 'goal-coverage-matrix.json')
    goal_state = load(repo / '.zoo-agent' / 'goal' / 'goal_state.json')
    loop_report = load(repo / '.zoo-agent' / 'runs' / 'run-complete' / 'goal-loop-report.json')
    next_goals = load(repo / '.zoo-agent' / 'runs' / 'run-complete' / 'next-goal-candidates.json')
    assert matrix['goal_completion_verdict'] == 'COMPLETED'
    assert goal_state['status'] == 'completed'
    assert loop_report['loop_status'] == 'converged'
    assert next_goals['next_goal_candidates']
    assert next_goals['auto_replace_goal'] is False
    assert next_goals['auto_execute'] is False


def test_partial_goal_enters_next_decomposition_loop() -> None:
    repo = init_repo('partial')
    goal_id = set_docs_goal(repo)
    decompose(repo, 'run-partial', goal_id, 'update docs/a.md docs/b.md')
    write_json(repo / '.zoo-agent' / 'runs' / 'run-partial' / 'leaf-results' / 'leaf-001.json', {'delivery_outcome': 'delivered'})
    proc = run([sys.executable, str(AGENT), 'aggregate', '--workspace', str(repo), '--run-id', 'run-partial', '--goal-id', goal_id], repo, check=False)
    assert proc.returncode == 10
    matrix = load(repo / '.zoo-agent' / 'runs' / 'run-partial' / 'goal-coverage-matrix.json')
    loop_report = load(repo / '.zoo-agent' / 'runs' / 'run-partial' / 'goal-loop-report.json')
    assert matrix['goal_completion_verdict'] in {'PARTIAL', 'NEEDS_REPLAN'}
    assert loop_report['loop_status'] == 'active'
    assert loop_report['next_action'] in {'next_decomposition_loop', 'continue_goal_driven_loop_or_refine_required_leaf'}


def test_max_iteration_forces_human_loop_decision() -> None:
    repo = init_repo('max-iteration')
    goal_id = set_docs_goal(repo)
    decompose(repo, 'run-max', goal_id, 'update docs/a.md docs/b.md')
    write_json(repo / '.zoo-agent' / 'runs' / 'run-max' / 'leaf-results' / 'leaf-001.json', {'delivery_outcome': 'delivered'})
    write_json(repo / '.zoo-agent' / 'runs' / 'run-max' / 'loop-state.json', {'iteration': 10, 'max_iterations': 10, 'status': 'active'})
    proc = run([sys.executable, str(AGENT), 'goal-loop', '--workspace', str(repo), '--run-id', 'run-max', '--goal-id', goal_id, '--max-iterations', '10'], repo, check=False)
    assert proc.returncode == 10
    report = load(repo / '.zoo-agent' / 'runs' / 'run-max' / 'goal-loop-report.json')
    goal_state = load(repo / '.zoo-agent' / 'goal' / 'goal_state.json')
    assert report['loop_status'] == 'waiting_human'
    assert goal_state['status'] in {'degraded', 'paused'}
    assert report['drift_detected'] is True


def test_big_task_without_goal_remains_blocked() -> None:
    repo = init_repo('missing-goal')
    proc = run(
        [
            sys.executable,
            str(AGENT),
            'plan-big',
            'add cross-module feature touching docs/a.md docs/b.md',
            '--workspace',
            str(repo),
            '--run-id',
            'run-missing-goal',
        ],
        repo,
        check=False,
    )
    assert proc.returncode == 10
    contract = load(repo / '.zoo-agent' / 'runs' / 'run-missing-goal' / 'big-task-contract.json')
    assert contract['readiness_verdict'] == 'BLOCKED_GOAL_UNCLEAR'
    assert not (repo / '.zoo-agent' / 'goal' / 'current-goal.json').exists()


def test_classifier_exposes_goal_loop_policy() -> None:
    repo = init_repo('classifier')
    proc = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'task_classifier.py'),
            'change public API response and database schema',
            '--workspace',
            str(repo),
        ],
        repo,
    )
    report = json.loads(proc.stdout)
    policy = report['big_task_policy']
    assert 'agent goal-loop' in policy['required_entrypoints']
    assert policy['codex_role'] == 'leaf_execution_backend_only'


def main() -> int:
    os.environ.setdefault('CODEX_HOME', 'D:/AI_DEV/codex_home')
    test_completed_goal_loop()
    test_partial_goal_enters_next_decomposition_loop()
    test_max_iteration_forces_human_loop_decision()
    test_big_task_without_goal_remains_blocked()
    test_classifier_exposes_goal_loop_policy()
    print('goal driven orchestrator tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
