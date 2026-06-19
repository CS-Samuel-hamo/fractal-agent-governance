#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'bin'
AGENT = 'agent.cmd' if os.name == 'nt' else 'agent'


def run(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    printable = ' '.join(str(part) for part in cmd)
    print(f'$ {printable}')
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.stdout:
        print(proc.stdout)
    if proc.returncode != 0:
        raise AssertionError(f'command failed with {proc.returncode}: {printable}')
    return proc


def temp_root() -> Path:
    configured = os.environ.get('AGENT_ALPHA_TEMP_ROOT')
    base = Path(configured) if configured else Path(tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    return base


def unique_dir(prefix: str) -> Path:
    stamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    path = temp_root() / f'{prefix}-{stamp}-{os.getpid()}'
    path.mkdir(parents=True, exist_ok=False)
    return path


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def cli_report(repo: Path, run_id: str, task_id: str) -> dict:
    return read_json(repo / '.zoo-agent' / 'runs' / run_id / 'cli-runtime' / f'{task_id}.json')


def init_repo(repo: Path, env: dict[str, str], *, docs: bool = False) -> None:
    write(repo / 'README.md', '# Demo\n\nTpy o.\n')
    write(repo / '.gitignore', '.zoo-agent/worktrees/\n')
    write(repo / 'AGENTS.md', '# Existing local instructions\n')
    write(repo / 'src' / 'example.py', 'def add(a, b):\n    return a + b\n')
    write(
        repo / 'tests' / 'test_example.py',
        'from src.example import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n',
    )
    if docs:
        write(repo / 'docs' / 'a.md', 'A\n')
        write(repo / 'docs' / 'b.md', 'B\n')
        write(repo / 'docs' / 'plan.md', 'Plan\n')
    run(['git', 'init'], repo, env)
    run(['git', 'config', 'user.name', 'real-usage-alpha'], repo, env)
    run(['git', 'config', 'user.email', 'real-usage-alpha@example.local'], repo, env)
    run(['git', 'add', '.'], repo, env)
    run(['git', 'commit', '-m', 'init'], repo, env)


def assert_bootstrap_outputs(repo: Path) -> None:
    required = [
        repo / '.zoo-agent' / 'bootstrap.lock',
        repo / '.zoo-agent' / 'project-profile.json',
        repo / '.zoo-agent' / 'project-readiness.json',
        repo / '.zoo-agent' / 'bootstrap-report.md',
    ]
    for path in required:
        assert path.exists(), f'missing bootstrap artifact: {path}'
    readiness = read_json(repo / '.zoo-agent' / 'project-readiness.json')
    assert 'safe_for_level_0_1_trial' in readiness or 'status' in readiness


def main() -> int:
    env = os.environ.copy()
    env['PATH'] = str(BIN) + os.pathsep + env.get('PATH', '')
    env['PYTHONIOENCODING'] = 'utf-8'

    run([AGENT, '--version'], ROOT, env)
    run([AGENT, '--help'], ROOT, env)

    existing = unique_dir('agent-existing-project-alpha')
    init_repo(existing, env, docs=True)
    src_hash = file_hash(existing / 'src' / 'example.py')
    test_hash = file_hash(existing / 'tests' / 'test_example.py')
    agents_before = (existing / 'AGENTS.md').read_text(encoding='utf-8')
    gitignore_before = (existing / '.gitignore').read_text(encoding='utf-8')

    run([AGENT, 'bootstrap', '--workspace', str(existing)], existing, env)
    run([AGENT, 'bootstrap', '--workspace', str(existing)], existing, env)
    assert_bootstrap_outputs(existing)
    assert (existing / 'AGENTS.md').read_text(encoding='utf-8') == agents_before
    assert (existing / '.gitignore').read_text(encoding='utf-8') == gitignore_before
    assert (existing / 'AGENTS.md.new').exists(), 'existing AGENTS.md should get a proposal'
    assert (existing / '.gitignore.agent.patch').exists(), 'existing .gitignore should get a patch proposal'
    assert file_hash(existing / 'src' / 'example.py') == src_hash
    assert file_hash(existing / 'tests' / 'test_example.py') == test_hash
    assert not (existing / '.zoo-agent' / 'runtime-status.json').exists()
    run([AGENT, 'status', '--workspace', str(existing), '--no-write'], existing, env)
    assert not (existing / '.zoo-agent' / 'runtime-status.json').exists()

    run(
        [
            AGENT,
            'run',
            '--workspace',
            str(existing),
            '--run-id',
            'run-fast',
            '--task-id',
            'task-fast',
            '--dry-run',
            'fix a typo in README',
        ],
        existing,
        env,
    )
    fast = cli_report(existing, 'run-fast', 'task-fast')
    assert fast['route'] == 'fast'
    skipped = set((fast.get('fast_path_report') or {}).get('skipped_governance') or [])
    for item in ['product_doc_generation', 'full_planning_loop', 'fractal_decomposition', 'governed_reviewer', 'merge_queue']:
        assert item in skipped, f'fast path did not record skipped governance: {item}'
    for metric in ['fast_path_pre_codex_overhead_ms', 'codex_execution_ms', 'total_wall_time_ms']:
        assert metric in fast, f'missing fast metric: {metric}'

    run(
        [
            AGENT,
            'run',
            '--workspace',
            str(existing),
            '--run-id',
            'run-code-worker-dry',
            '--task-id',
            'task-code-worker-dry',
            '--allowed-file',
            'src/example.py',
            '--allowed-file',
            'tests/test_example.py',
            '--test-command',
            'python -m pytest',
            '--worker-dry-run',
            'update add so it also accepts numeric strings like add 1 2 and add a test',
        ],
        existing,
        env,
    )
    code = cli_report(existing, 'run-code-worker-dry', 'task-code-worker-dry')
    assert code['route'] in {'fast', 'parallel'}, f'unexpected small code route: {code["route"]}'
    assert code['route'] != 'governed', 'small bounded code task should not be governed'
    assert file_hash(existing / 'src' / 'example.py') == src_hash
    assert file_hash(existing / 'tests' / 'test_example.py') == test_hash

    new_project = unique_dir('agent-new-project-alpha')
    run([AGENT, 'bootstrap', '--workspace', str(new_project)], new_project, env)
    for rel in ['.git', 'README.md', 'AGENTS.md', '.gitignore', '.zoo-agent/project-profile.json', '.zoo-agent/project-readiness.json', '.zoo-agent/bootstrap-report.md', '.zoo-agent/bootstrap.lock']:
        assert (new_project / rel).exists(), f'missing new project artifact: {rel}'
    assert (new_project / '.zoo-agent' / 'TASKS.md').exists() or (new_project / 'TASKS.md').exists()
    run(
        [
            AGENT,
            'run',
            '--workspace',
            str(new_project),
            '--run-id',
            'run-new-hello',
            '--task-id',
            'task-new-hello',
            '--dry-run',
            'create a minimal hello world entry file only',
        ],
        new_project,
        env,
    )
    new_run = cli_report(new_project, 'run-new-hello', 'task-new-hello')
    assert new_run['route'] == 'fast'

    parallel = unique_dir('agent-parallel-alpha')
    write(parallel / 'docs' / 'a.md', 'A\n')
    write(parallel / 'docs' / 'b.md', 'B\n')
    run(['git', 'init'], parallel, env)
    run(['git', 'config', 'user.name', 'real-usage-alpha'], parallel, env)
    run(['git', 'config', 'user.email', 'real-usage-alpha@example.local'], parallel, env)
    run(['git', 'add', '.'], parallel, env)
    run(['git', 'commit', '-m', 'init'], parallel, env)
    run([AGENT, 'bootstrap', '--workspace', str(parallel)], parallel, env)
    run(
        [
            AGENT,
            'run',
            '--workspace',
            str(parallel),
            '--run-id',
            'run-parallel',
            '--task-id',
            'task-parallel',
            '--dry-run',
            'update docs/a.md and docs/b.md independently',
        ],
        parallel,
        env,
    )
    par = cli_report(parallel, 'run-parallel', 'task-parallel')
    assert par['route'] == 'parallel' or par.get('parallel_denial_reason'), 'parallel path must execute or explain denial'

    run(
        [
            AGENT,
            'run',
            '--workspace',
            str(existing),
            '--run-id',
            'run-governed',
            '--task-id',
            'task-governed',
            '--dry-run',
            'change public API response and database schema',
        ],
        existing,
        env,
    )
    governed = cli_report(existing, 'run-governed', 'task-governed')
    assert governed['route'] == 'governed'
    assert governed['execution']['status'] == 'dry_run'
    assert file_hash(existing / 'src' / 'example.py') == src_hash

    loop_state = existing / '.zoo-agent' / 'loop_state.json'
    loop_state.write_text(
        json.dumps({'iteration': 1, 'max_iteration': 1, 'status': 'active', 'drift_detected': False}, indent=2),
        encoding='utf-8',
    )
    run(
        [
            AGENT,
            'run',
            '--workspace',
            str(existing),
            '--run-id',
            'run-loop',
            '--task-id',
            'task-loop',
            '--dry-run',
            '--max-iteration',
            '1',
            'optimize local README wording',
        ],
        existing,
        env,
    )
    loop = cli_report(existing, 'run-loop', 'task-loop')
    assert loop.get('local_optimization_deferred') is True

    run(
        [
            AGENT,
            'run',
            '--workspace',
            str(existing),
            '--run-id',
            'run-doc-only',
            '--task-id',
            'task-doc-only',
            '--allowed-file',
            'docs/plan.md',
            '--dry-run',
            'implement validation in docs/plan.md',
        ],
        existing,
        env,
    )
    doc_only = cli_report(existing, 'run-doc-only', 'task-doc-only')
    assert doc_only.get('doc_only_task') is True
    assert doc_only.get('code_delivery_gate', {}).get('status') == 'fail'

    worktree = existing / '.zoo-agent' / 'worktrees' / 'run-rollback' / 'task-rollback' / 'attempt-1'
    run(['git', 'worktree', 'add', '-b', f'zoo/real-usage-alpha/task-rollback-{os.getpid()}', str(worktree), 'HEAD'], existing, env)
    evidence_dir = existing / '.zoo-agent' / 'runs' / 'run-rollback' / 'optimistic-runs'
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / 'task-rollback.json').write_text(json.dumps({'task_id': 'task-rollback', 'attempts': [{'worktree': str(worktree)}]}, indent=2), encoding='utf-8')
    run([AGENT, 'rollback', '--workspace', str(existing), '--run-id', 'run-rollback', '--task-id', 'task-rollback', '--dry-run'], existing, env)
    rollback = read_json(existing / '.zoo-agent' / 'runs' / 'run-rollback' / 'rollback' / 'task-rollback.json')
    assert rollback['status'] == 'dry_run'
    assert worktree.exists(), 'rollback dry-run removed a worktree'

    assert file_hash(existing / 'src' / 'example.py') == src_hash
    assert file_hash(existing / 'tests' / 'test_example.py') == test_hash
    print('local alpha real usage test pass')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
