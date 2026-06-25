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


def run(
    cmd: list[str], cwd: Path, *, check: bool = True, env: dict[str, str] | None = None, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        input=stdin,
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


def init_repo(tmp: Path, env: dict[str, str]) -> None:
    run(['git', 'init'], tmp, env=env)
    run(['git', 'config', 'user.email', 'runtime-test@example.local'], tmp, env=env)
    run(['git', 'config', 'user.name', 'Runtime Test'], tmp, env=env)
    (tmp / 'README.md').write_text('# Demo\n\nTypoo.\n', encoding='utf-8')
    (tmp / 'docs').mkdir()
    (tmp / 'docs' / 'a.md').write_text('# A\n', encoding='utf-8')
    (tmp / 'docs' / 'b.md').write_text('# B\n', encoding='utf-8')
    (tmp / 'src').mkdir()
    (tmp / 'src' / 'api.py').write_text('SCHEMA = {}\n', encoding='utf-8')
    run(['git', 'add', '.'], tmp, env=env)
    run(['git', 'commit', '-m', 'init'], tmp, env=env)


def cli_report(repo: Path, run_id: str, task_id: str) -> dict:
    return load(repo / '.zoo-agent' / 'runs' / run_id / 'cli-runtime' / f'{task_id}.json')


def test_bootstrap_idempotency(repo: Path, env: dict[str, str]) -> None:
    first = run([sys.executable, str(AGENT), 'bootstrap', '--workspace', str(repo), '--force'], repo, env=env)
    assert sorted(json.loads(first.stdout)) == ['goal', 'progress', 'result']
    lock = repo / '.zoo-agent' / 'bootstrap.lock'
    assert lock.exists(), 'bootstrap.lock was not created'
    second = run([sys.executable, str(AGENT), 'bootstrap', '--workspace', str(repo)], repo, env=env)
    second_payload = json.loads(second.stdout)
    assert second_payload['progress'] == 'already bootstrapped', 'second bootstrap did not honor bootstrap.lock'


def test_interactive_natural_language(repo: Path, env: dict[str, str]) -> None:
    interactive_env = dict(env)
    interactive_env['AGENT_INTERACTIVE_DRY_RUN'] = '1'
    run([sys.executable, str(AGENT)], repo, env=interactive_env, stdin='Fix README typo\n/exit\n')
    reports = sorted(
        (repo / '.zoo-agent' / 'runs').glob('run-*/cli-runtime/*.json'), key=lambda path: path.stat().st_mtime
    )
    assert reports, 'interactive natural language did not create a CLI runtime report'
    payload = load(reports[-1])
    assert payload.get('input') == 'Fix README typo', 'interactive input was not routed as agent run input'


def test_agent_task_alias(repo: Path, env: dict[str, str]) -> None:
    run(
        [
            sys.executable,
            str(AGENT),
            'Fix README typo',
            '--workspace',
            str(repo),
            '--run-id',
            'run-alias',
            '--task-id',
            'task-alias',
            '--dry-run',
        ],
        repo,
        env=env,
    )
    run(
        [
            sys.executable,
            str(AGENT),
            'run',
            '--workspace',
            str(repo),
            '--run-id',
            'run-command',
            '--task-id',
            'task-command',
            '--dry-run',
            'Fix',
            'README',
            'typo',
        ],
        repo,
        env=env,
    )
    alias = cli_report(repo, 'run-alias', 'task-alias')
    command = cli_report(repo, 'run-command', 'task-command')
    assert alias.get('input') == command.get('input') == 'Fix README typo'
    assert alias.get('selected_path') == command.get('selected_path')


def test_fast_path_contract(repo: Path) -> None:
    payload = cli_report(repo, 'run-alias', 'task-alias')
    assert payload.get('selected_path') == 'fast', 'README typo should route fast'
    fast = payload.get('fast_path_report') or {}
    assert fast.get('route') == 'fast'
    skipped = set(fast.get('skipped_governance') or [])
    for item in [
        'product_doc_generation',
        'full_planning_loop',
        'fractal_decomposition',
        'implementation_queue',
        'governed_reviewer',
        'parent_aggregation',
        'merge_queue',
    ]:
        assert item in skipped, f'fast path did not declare skipped governance: {item}'
    run_dir = repo / '.zoo-agent' / 'runs' / 'run-alias'
    for artifact in ['implementation-queue.json', 'gpt-review.json', 'merge-queue.json', 'parent-aggregation.json']:
        assert not (run_dir / artifact).exists(), f'fast path wrote governed artifact: {artifact}'
    for metric in ['fast_path_pre_backend_overhead_ms', 'backend_execution_ms', 'total_wall_time_ms']:
        assert metric in payload, f'missing fast timing metric: {metric}'


def test_parallel_docs_policy(repo: Path, env: dict[str, str]) -> None:
    run(
        [
            sys.executable,
            str(AGENT),
            'run',
            '--workspace',
            str(repo),
            '--run-id',
            'run-parallel',
            '--task-id',
            'task-parallel',
            '--parallel',
            '--dry-run',
            'Update docs/a.md',
            'Update docs/b.md',
        ],
        repo,
        env=env,
    )
    payload = cli_report(repo, 'run-parallel', 'task-parallel')
    assert payload.get('selected_path') == 'parallel' or payload.get('parallel_denial_reason'), (
        'parallel route lacked pass or denial reason'
    )


def test_schema_task_governed(repo: Path, env: dict[str, str]) -> None:
    run(
        [
            sys.executable,
            str(AGENT),
            'run',
            '--workspace',
            str(repo),
            '--run-id',
            'run-governed',
            '--task-id',
            'task-governed',
            '--dry-run',
            'Change API schema DTO contract',
        ],
        repo,
        env=env,
    )
    payload = cli_report(repo, 'run-governed', 'task-governed')
    assert payload.get('selected_path') == 'governed', 'API/schema/DTO task should route governed'


def test_rollback_dry_run(repo: Path, env: dict[str, str]) -> None:
    worktree = repo / '.zoo-agent' / 'worktrees' / 'run-rollback' / 'task-rollback' / 'attempt-1'
    run(['git', 'worktree', 'add', '-b', 'zoo/test-rollback/task-rollback', str(worktree), 'HEAD'], repo, env=env)
    evidence = repo / '.zoo-agent' / 'runs' / 'run-rollback' / 'optimistic-runs'
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / 'task-rollback.json').write_text(
        json.dumps({'task_id': 'task-rollback', 'attempts': [{'worktree': str(worktree)}]}, indent=2),
        encoding='utf-8',
    )
    run(
        [
            sys.executable,
            str(AGENT),
            'rollback',
            '--workspace',
            str(repo),
            '--run-id',
            'run-rollback',
            '--task-id',
            'task-rollback',
        ],
        repo,
        env=env,
    )
    assert worktree.exists(), 'rollback default dry-run removed the worktree'


def test_status_no_write(repo: Path, env: dict[str, str]) -> None:
    status_path = repo / '.zoo-agent' / 'runs' / 'run-command' / 'runtime-status.json'
    if status_path.exists():
        status_path.unlink()
    run(
        [
            sys.executable,
            str(AGENT),
            'status',
            '--workspace',
            str(repo),
            '--run-id',
            'run-command',
            '--no-write',
        ],
        repo,
        env=env,
    )
    assert not status_path.exists(), 'status --no-write created runtime-status.json'


def test_loop_convergence_followup(repo: Path, env: dict[str, str]) -> None:
    loop_path = repo / '.zoo-agent' / 'loop_state.json'
    loop_path.write_text(
        json.dumps({'iteration': 10, 'max_iteration': 10, 'status': 'active', 'drift_detected': False}, indent=2),
        encoding='utf-8',
    )
    run(
        [
            sys.executable,
            str(AGENT),
            'run',
            '--workspace',
            str(repo),
            '--run-id',
            'run-loop',
            '--task-id',
            'task-loop',
            '--dry-run',
            'optimize local README wording',
        ],
        repo,
        env=env,
    )
    payload = cli_report(repo, 'run-loop', 'task-loop')
    assert payload.get('loop_state', {}).get('status') == 'diverging'
    assert payload.get('local_optimization_deferred') is True
    assert payload.get('classification', {}).get('follow_up_reason') == 'loop_convergence_force_follow_up'


def test_metrics_keys(repo: Path) -> None:
    metrics = load(repo / '.zoo-agent' / 'metrics' / 'agent-runtime-v4.json').get('metrics') or {}
    for key in [
        'fast_path_rate',
        'parallel_execution_rate',
        'governed_path_rate',
        'fast_path_pre_backend_overhead_ms',
        'backend_execution_latency',
        'doc_overproduction_rate',
        'code_delivery_rate',
        'parallel_denial_count',
        'loop_converged_count',
        'local_optimization_deferred_count',
    ]:
        assert key in metrics, f'missing metric: {key}'


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='zoo-cli-runtime-paths-')).resolve()
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(tmp / '.codex-home'))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)
    print('Acceptance repo:', tmp)
    init_repo(tmp, env)
    test_bootstrap_idempotency(tmp, env)
    test_interactive_natural_language(tmp, env)
    test_agent_task_alias(tmp, env)
    test_fast_path_contract(tmp)
    test_parallel_docs_policy(tmp, env)
    test_schema_task_governed(tmp, env)
    test_rollback_dry_run(tmp, env)
    test_status_no_write(tmp, env)
    test_loop_convergence_followup(tmp, env)
    test_metrics_keys(tmp)
    print('CLI runtime path acceptance tests passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
