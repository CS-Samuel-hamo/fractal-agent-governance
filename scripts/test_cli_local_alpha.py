#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'


def run(cmd: list[str], cwd: Path, *, env: dict[str, str], check: bool = True, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def init_existing_repo(env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix='zoo-local-alpha-existing-')).resolve()
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'alpha@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Local Alpha'], repo, env=env)
    (repo / 'src').mkdir()
    (repo / 'tests').mkdir()
    (repo / 'docs').mkdir()
    (repo / 'README.md').write_text('# Existing Demo\n\nTypoo.\n', encoding='utf-8')
    (repo / '.gitignore').write_text('*.tmp\n', encoding='utf-8')
    (repo / 'src' / 'app.py').write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')
    (repo / 'tests' / 'test_app.py').write_text('from src.app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n', encoding='utf-8')
    (repo / 'docs' / 'a.md').write_text('# A\n', encoding='utf-8')
    (repo / 'docs' / 'b.md').write_text('# B\n', encoding='utf-8')
    (repo / 'docs' / 'plan.md').write_text('# Plan\n', encoding='utf-8')
    run(['git', 'add', '.'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def cli_report(repo: Path, run_id: str, task_id: str) -> dict:
    return load(repo / '.zoo-agent' / 'runs' / run_id / 'cli-runtime' / f'{task_id}.json')


def assert_artifacts(repo: Path) -> None:
    for rel in [
        '.zoo-agent/project-profile.json',
        '.zoo-agent/project-readiness.json',
        '.zoo-agent/bootstrap-report.md',
        '.zoo-agent/bootstrap.lock',
        'AGENTS.md',
        '.gitignore.agent.patch',
    ]:
        assert (repo / rel).exists(), f'missing bootstrap artifact: {rel}'


def main() -> int:
    try:
        env = os.environ.copy()
        env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='zoo-local-alpha-codex-home-')).resolve()))
        Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)

        help_result = run([sys.executable, str(AGENT), '--help'], ROOT, env=env)
        assert 'bootstrap' in help_result.stdout
        version_result = run([sys.executable, str(AGENT), '--version'], ROOT, env=env)
        assert '0.4.0-local-alpha' in version_result.stdout

        existing = init_existing_repo(env)
        src_hash = sha(existing / 'src' / 'app.py')
        test_hash = sha(existing / 'tests' / 'test_app.py')
        first_bootstrap = run([sys.executable, str(AGENT), 'bootstrap', '--workspace', str(existing)], existing, env=env)
        assert_artifacts(existing)
        assert 'safe_for_level_0_1_trial' in first_bootstrap.stdout
        assert sha(existing / 'src' / 'app.py') == src_hash
        assert sha(existing / 'tests' / 'test_app.py') == test_hash

        agents_hash = sha(existing / 'AGENTS.md')
        second_bootstrap = run([sys.executable, str(AGENT), 'bootstrap', '--workspace', str(existing)], existing, env=env)
        assert 'already_bootstrapped' in second_bootstrap.stdout
        assert sha(existing / 'AGENTS.md') == agents_hash
        assert sha(existing / 'src' / 'app.py') == src_hash
        assert sha(existing / 'tests' / 'test_app.py') == test_hash

        new_project = Path(tempfile.mkdtemp(prefix='zoo-local-alpha-new-')).resolve()
        run([sys.executable, str(AGENT), 'bootstrap', '--workspace', str(new_project)], new_project, env=env)
        for rel in ['.git', 'README.md', 'AGENTS.md', '.gitignore', '.zoo-agent/project-profile.json', '.zoo-agent/project-readiness.json', '.zoo-agent/bootstrap-report.md', '.zoo-agent/bootstrap.lock', '.zoo-agent/TASKS.md']:
            assert (new_project / rel).exists(), f'missing new-project artifact: {rel}'
        assert not (new_project / 'src').exists(), 'new bootstrap should not generate business source code'

        run([sys.executable, str(AGENT), 'fix typo in README', '--workspace', str(existing), '--run-id', 'run-shorthand', '--task-id', 'task-shorthand', '--dry-run'], existing, env=env)
        assert cli_report(existing, 'run-shorthand', 'task-shorthand').get('input') == 'fix typo in README'

        interactive_env = dict(env)
        interactive_env['AGENT_INTERACTIVE_DRY_RUN'] = '1'
        run([sys.executable, str(AGENT)], existing, env=interactive_env, stdin='fix typo in README\n/exit\n')

        run([sys.executable, str(AGENT), 'fix typo in README', '--workspace', str(existing), '--run-id', 'run-fast', '--task-id', 'task-fast', '--dry-run'], existing, env=env)
        fast = cli_report(existing, 'run-fast', 'task-fast')
        assert fast.get('route') == 'fast'
        assert fast.get('fast_path_report', {}).get('route') == 'fast'
        assert fast.get('fast_path_pre_codex_overhead_ms') is not None

        run([sys.executable, str(AGENT), 'run', '--workspace', str(existing), '--run-id', 'run-parallel', '--task-id', 'task-parallel', '--parallel', '--dry-run', 'update docs/a.md', 'update docs/b.md'], existing, env=env)
        parallel = cli_report(existing, 'run-parallel', 'task-parallel')
        assert parallel.get('route') == 'parallel' or parallel.get('parallel_denial_reason')

        run([sys.executable, str(AGENT), 'change public API response and database schema', '--workspace', str(existing), '--run-id', 'run-governed', '--task-id', 'task-governed', '--dry-run'], existing, env=env)
        governed = cli_report(existing, 'run-governed', 'task-governed')
        assert governed.get('route') == 'governed'

        status_path = existing / '.zoo-agent' / 'runs' / 'run-fast' / 'runtime-status.json'
        if status_path.exists():
            status_path.unlink()
        run([sys.executable, str(AGENT), 'status', '--workspace', str(existing), '--run-id', 'run-fast', '--no-write'], existing, env=env)
        assert not status_path.exists(), 'status --no-write wrote runtime-status.json'

        worktree = existing / '.zoo-agent' / 'worktrees' / 'run-rollback' / 'task-rollback' / 'attempt-1'
        run(['git', 'worktree', 'add', '-b', 'zoo/local-alpha/task-rollback', str(worktree), 'HEAD'], existing, env=env)
        evidence_dir = existing / '.zoo-agent' / 'runs' / 'run-rollback' / 'optimistic-runs'
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / 'task-rollback.json').write_text(json.dumps({'task_id': 'task-rollback', 'attempts': [{'worktree': str(worktree)}]}, indent=2), encoding='utf-8')
        run([sys.executable, str(AGENT), 'rollback', '--workspace', str(existing), '--run-id', 'run-rollback', '--task-id', 'task-rollback', '--dry-run'], existing, env=env)
        assert worktree.exists(), 'rollback --dry-run removed worktree'

        loop_state = existing / '.zoo-agent' / 'loop_state.json'
        loop_state.write_text(json.dumps({'iteration': 10, 'max_iteration': 10, 'status': 'active', 'drift_detected': False}, indent=2), encoding='utf-8')
        run([sys.executable, str(AGENT), 'optimize local README wording', '--workspace', str(existing), '--run-id', 'run-loop', '--task-id', 'task-loop', '--dry-run'], existing, env=env)
        loop = cli_report(existing, 'run-loop', 'task-loop')
        assert loop.get('loop_state', {}).get('status') == 'diverging'
        assert loop.get('local_optimization_deferred') is True

        run([sys.executable, str(AGENT), 'implement validation in docs/plan.md', '--workspace', str(existing), '--run-id', 'run-doc-only', '--task-id', 'task-doc-only', '--dry-run'], existing, env=env)
        doc_only = cli_report(existing, 'run-doc-only', 'task-doc-only')
        assert doc_only.get('doc_only_task') is True
        assert doc_only.get('code_delivery_gate', {}).get('status') == 'fail'
        metrics = load(existing / '.zoo-agent' / 'metrics' / 'agent-runtime-v4.json').get('metrics') or {}
        assert 'doc_only_task_rate' in metrics

        assert sha(existing / 'src' / 'app.py') == src_hash, 'business source modified during tests/bootstrap'
        assert sha(existing / 'tests' / 'test_app.py') == test_hash, 'business tests modified during tests/bootstrap'

        print('local alpha test pass')
        return 0
    except Exception as exc:
        print(f'local alpha test fail: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
