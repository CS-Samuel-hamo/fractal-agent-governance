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


def run_may_fail(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
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


def write_fast_cli_report(
    repo: Path,
    run_id: str,
    task_id: str,
    text: str,
    *,
    tests_status: str = 'not_applicable',
    allowed_files: list[str] | None = None,
) -> None:
    write(
        repo / '.zoo-agent' / 'runs' / run_id / 'cli-runtime' / f'{task_id}.json',
        json.dumps(
            {
                'schema_version': '4.0',
                'generated_by': 'test_cli_real_usage_alpha.py',
                'run_id': run_id,
                'task_id': task_id,
                'workspace': str(repo),
                'input': text,
                'route': 'fast',
                'selected_path': 'fast',
                'classification': {'allowed_files': allowed_files or ['README.md'], 'denied_files': ['.env', '.env.*', '.codex/**']},
                'execution': {'status': 'merge_candidate_partial', 'returncode': 0},
                'scope_guard_status': 'pass',
                'tests_status': tests_status,
            },
            indent=2,
        ),
    )


def write_fast_optimistic_report(repo: Path, run_id: str, task_id: str, *, changed_files: list[str], final_message: str = 'Done.') -> None:
    write(
        repo / '.zoo-agent' / 'runs' / run_id / 'optimistic-runs' / f'{task_id}.json',
        json.dumps(
            {
                'status': 'merge_candidate_partial',
                'attempts': [
                    {
                        'task_id': task_id,
                        'codex_worker': {'returncode': 0, 'timed_out': False},
                        'test_results': [],
                        'collected_result': {
                            'scope_guard': {'status': 'pass'},
                            'git_diff_name_only': changed_files,
                            'final_message': final_message,
                        },
                        'policy': {'status': 'merge_candidate_partial'},
                    }
                ],
            },
            indent=2,
        ),
    )


def capture_baseline(
    repo: Path,
    run_id: str,
    task_id: str,
    env: dict[str, str],
    *,
    text: str,
    task_type: str = 'docs',
    allowed_files: list[str] | None = None,
) -> dict:
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'capture_task_baseline.py'),
        '--workspace',
        str(repo),
        '--run-id',
        run_id,
        '--task-id',
        task_id,
        '--route',
        'fast',
        '--task-type',
        task_type,
        '--input-text',
        text,
    ]
    for item in allowed_files or ['README.md']:
        command.extend(['--allowed-file', item])
    command.extend(['--denied-file', '.env', '--denied-file', '.env.*'])
    run(
        command,
        ROOT,
        env,
    )
    return read_json(repo / '.zoo-agent' / 'runs' / run_id / 'tasks' / task_id / 'task-baseline.json')


def compare_baseline(repo: Path, run_id: str, task_id: str, env: dict[str, str]) -> dict:
    baseline = repo / '.zoo-agent' / 'runs' / run_id / 'tasks' / task_id / 'task-baseline.json'
    run_may_fail(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'compare_task_baseline.py'),
            '--baseline',
            str(baseline),
            '--workspace',
            str(repo),
            '--denied-file',
            '.env',
            '--denied-file',
            '.env.*',
        ],
        ROOT,
        env,
    )
    return read_json(repo / '.zoo-agent' / 'runs' / run_id / 'tasks' / task_id / 'task-delta.json')


def blocker_types(payload: dict) -> set[str]:
    return {str(item.get('type')) for item in payload.get('blockers') or [] if isinstance(item, dict)}


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

    no_diff = unique_dir('agent-no-diff-alpha')
    write(no_diff / 'README.md', '# Demo\n\nTpy o.\n')
    run(['git', 'init'], no_diff, env)
    run(['git', 'config', 'user.name', 'real-usage-alpha'], no_diff, env)
    run(['git', 'config', 'user.email', 'real-usage-alpha@example.local'], no_diff, env)
    run(['git', 'add', 'README.md'], no_diff, env)
    run(['git', 'commit', '-m', 'init'], no_diff, env)
    run([AGENT, 'bootstrap', '--workspace', str(no_diff)], no_diff, env)
    write_fast_cli_report(no_diff, 'run-no-diff', 'task-no-diff', 'fix a typo in README', allowed_files=['README.md'])
    capture_baseline(no_diff, 'run-no-diff', 'task-no-diff', env, text='fix a typo in README', task_type='docs', allowed_files=['README.md'])
    write_fast_optimistic_report(no_diff, 'run-no-diff', 'task-no-diff', changed_files=[], final_message='Done.')
    no_diff_delta = compare_baseline(no_diff, 'run-no-diff', 'task-no-diff', env)
    assert 'AGENTS.md' in no_diff_delta['unchanged_existing_diff'] or 'AGENTS.md' in no_diff_delta['governance_artifacts']
    assert not no_diff_delta['business_candidate_files']
    proc = run_may_fail(
        [sys.executable, str(ROOT / 'scripts' / 'check_delivery_outcome.py'), '--workspace', str(no_diff), '--run-id', 'run-no-diff', '--task-id', 'task-no-diff'],
        ROOT,
        env,
    )
    assert proc.returncode == 1, 'no-diff fast run must fail delivery outcome'
    no_diff_outcome = read_json(no_diff / '.zoo-agent' / 'runs' / 'run-no-diff' / 'delivery-outcome.json')
    assert no_diff_outcome['delivery_outcome'] == 'no_delivery'
    proc = run_may_fail(
        [sys.executable, str(ROOT / 'scripts' / 'check_fast_path_gate.py'), '--workspace', str(no_diff), '--run-id', 'run-no-diff', '--task-id', 'task-no-diff'],
        ROOT,
        env,
    )
    assert proc.returncode == 20, 'no_delivery must fail fast path gate'
    no_diff_gate = read_json(no_diff / '.zoo-agent' / 'runs' / 'run-no-diff' / 'fast-path-gate.json')
    assert no_diff_gate['verdict'] == 'FAST_NO_DELIVERY'

    docs_delivered = unique_dir('agent-docs-delivered-alpha')
    write(docs_delivered / 'README.md', '# Demo\n\nTpy o.\n')
    run(['git', 'init'], docs_delivered, env)
    run(['git', 'config', 'user.name', 'real-usage-alpha'], docs_delivered, env)
    run(['git', 'config', 'user.email', 'real-usage-alpha@example.local'], docs_delivered, env)
    run(['git', 'add', 'README.md'], docs_delivered, env)
    run(['git', 'commit', '-m', 'init'], docs_delivered, env)
    run([AGENT, 'bootstrap', '--workspace', str(docs_delivered)], docs_delivered, env)
    write_fast_cli_report(docs_delivered, 'run-docs-delivered', 'task-docs-delivered', 'fix typo in README', tests_status='not_applicable')
    capture_baseline(docs_delivered, 'run-docs-delivered', 'task-docs-delivered', env, text='fix typo in README', task_type='docs')
    write(docs_delivered / 'README.md', '# Demo\n\nTypo fixed.\n')
    write_fast_optimistic_report(docs_delivered, 'run-docs-delivered', 'task-docs-delivered', changed_files=['README.md'])
    docs_delta = compare_baseline(docs_delivered, 'run-docs-delivered', 'task-docs-delivered', env)
    assert docs_delta['business_candidate_files'] == ['README.md']
    run(
        [sys.executable, str(ROOT / 'scripts' / 'check_delivery_outcome.py'), '--workspace', str(docs_delivered), '--run-id', 'run-docs-delivered', '--task-id', 'task-docs-delivered'],
        ROOT,
        env,
    )
    docs_outcome = read_json(docs_delivered / '.zoo-agent' / 'runs' / 'run-docs-delivered' / 'delivery-outcome.json')
    assert docs_outcome['delivery_outcome'] == 'delivered'
    run(
        [sys.executable, str(ROOT / 'scripts' / 'check_fast_path_gate.py'), '--workspace', str(docs_delivered), '--run-id', 'run-docs-delivered', '--task-id', 'task-docs-delivered'],
        ROOT,
        env,
    )
    docs_gate = read_json(docs_delivered / '.zoo-agent' / 'runs' / 'run-docs-delivered' / 'fast-path-gate.json')
    assert docs_gate['verdict'] == 'FAST_DELIVERED'
    run([sys.executable, str(ROOT / 'scripts' / 'runtime_review.py'), '--workspace', str(docs_delivered), '--run-id', 'run-docs-delivered'], ROOT, env)
    docs_review = read_json(docs_delivered / '.zoo-agent' / 'runs' / 'run-docs-delivered' / 'runtime-review.json')
    assert docs_review['status'] == 'pass'
    assert docs_review['verdict'] == 'FAST_DELIVERED'

    runtime_only = unique_dir('agent-runtime-only-alpha')
    init_repo(runtime_only, env)
    write_fast_cli_report(
        runtime_only,
        'run-runtime-only',
        'task-runtime-only',
        'fix a local bug in src/example.py',
        tests_status='passed',
        allowed_files=['src/example.py'],
    )
    capture_baseline(runtime_only, 'run-runtime-only', 'task-runtime-only', env, text='fix a local bug in src/example.py', task_type='coding', allowed_files=['src/example.py'])
    write(runtime_only / '.zoo-agent' / 'runs' / 'run-runtime-only' / 'evidence.txt', 'runtime only\n')
    write_fast_optimistic_report(runtime_only, 'run-runtime-only', 'task-runtime-only', changed_files=['.zoo-agent/tmp/evidence.txt'])
    runtime_delta = compare_baseline(runtime_only, 'run-runtime-only', 'task-runtime-only', env)
    assert runtime_delta['runtime_artifacts']
    proc = run_may_fail(
        [sys.executable, str(ROOT / 'scripts' / 'check_delivery_outcome.py'), '--workspace', str(runtime_only), '--run-id', 'run-runtime-only', '--task-id', 'task-runtime-only'],
        ROOT,
        env,
    )
    assert proc.returncode == 1
    runtime_outcome = read_json(runtime_only / '.zoo-agent' / 'runs' / 'run-runtime-only' / 'delivery-outcome.json')
    assert runtime_outcome['delivery_outcome'] == 'no_delivery'

    governance_only = unique_dir('agent-governance-only-alpha')
    init_repo(governance_only, env)
    write_fast_cli_report(governance_only, 'run-governance-only', 'task-governance-only', 'fix local bug', tests_status='passed', allowed_files=['src/example.py'])
    capture_baseline(governance_only, 'run-governance-only', 'task-governance-only', env, text='fix local bug', task_type='coding', allowed_files=['src/example.py'])
    write(governance_only / 'AGENTS.md', '# Existing local instructions\n\nExtra governance note.\n')
    write_fast_optimistic_report(governance_only, 'run-governance-only', 'task-governance-only', changed_files=['AGENTS.md'])
    governance_delta = compare_baseline(governance_only, 'run-governance-only', 'task-governance-only', env)
    assert governance_delta['governance_artifacts'] == ['AGENTS.md']
    proc = run_may_fail(
        [sys.executable, str(ROOT / 'scripts' / 'check_delivery_outcome.py'), '--workspace', str(governance_only), '--run-id', 'run-governance-only', '--task-id', 'task-governance-only'],
        ROOT,
        env,
    )
    assert proc.returncode == 1
    governance_outcome = read_json(governance_only / '.zoo-agent' / 'runs' / 'run-governance-only' / 'delivery-outcome.json')
    assert governance_outcome['delivery_outcome'] == 'no_delivery'

    bootstrap_delivery = unique_dir('agent-bootstrap-delivery-alpha')
    init_repo(bootstrap_delivery, env)
    write_fast_cli_report(bootstrap_delivery, 'run-bootstrap-delivery', 'task-bootstrap-delivery', 'bootstrap project', tests_status='not_applicable', allowed_files=['AGENTS.md'])
    capture_baseline(bootstrap_delivery, 'run-bootstrap-delivery', 'task-bootstrap-delivery', env, text='bootstrap project', task_type='bootstrap', allowed_files=['AGENTS.md'])
    write(bootstrap_delivery / 'AGENTS.md', '# Existing local instructions\n\nBootstrap update.\n')
    write_fast_optimistic_report(bootstrap_delivery, 'run-bootstrap-delivery', 'task-bootstrap-delivery', changed_files=['AGENTS.md'])
    compare_baseline(bootstrap_delivery, 'run-bootstrap-delivery', 'task-bootstrap-delivery', env)
    run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'check_delivery_outcome.py'),
            '--workspace',
            str(bootstrap_delivery),
            '--run-id',
            'run-bootstrap-delivery',
            '--task-id',
            'task-bootstrap-delivery',
            '--task-type',
            'bootstrap',
        ],
        ROOT,
        env,
    )
    bootstrap_outcome = read_json(bootstrap_delivery / '.zoo-agent' / 'runs' / 'run-bootstrap-delivery' / 'delivery-outcome.json')
    assert bootstrap_outcome['delivery_outcome'] == 'delivered'

    no_op = unique_dir('agent-no-op-alpha')
    init_repo(no_op, env)
    write_fast_cli_report(no_op, 'run-no-op', 'task-no-op', 'fix specified typo in README', tests_status='not_applicable')
    capture_baseline(no_op, 'run-no-op', 'task-no-op', env, text='fix specified typo in README', task_type='docs')
    write_fast_optimistic_report(
        no_op,
        'run-no-op',
        'task-no-op',
        changed_files=[],
        final_message='Checked README.md for the specified typo and no typo found; no changes needed after reviewing README.md.',
    )
    compare_baseline(no_op, 'run-no-op', 'task-no-op', env)
    run([sys.executable, str(ROOT / 'scripts' / 'check_delivery_outcome.py'), '--workspace', str(no_op), '--run-id', 'run-no-op', '--task-id', 'task-no-op'], ROOT, env)
    no_op_outcome = read_json(no_op / '.zoo-agent' / 'runs' / 'run-no-op' / 'delivery-outcome.json')
    assert no_op_outcome['delivery_outcome'] == 'no_op_with_evidence'
    run([sys.executable, str(ROOT / 'scripts' / 'check_fast_path_gate.py'), '--workspace', str(no_op), '--run-id', 'run-no-op', '--task-id', 'task-no-op'], ROOT, env)
    no_op_gate = read_json(no_op / '.zoo-agent' / 'runs' / 'run-no-op' / 'fast-path-gate.json')
    assert no_op_gate['verdict'] == 'FAST_NO_OP_ACCEPTED'

    empty_no_op = unique_dir('agent-empty-no-op-alpha')
    init_repo(empty_no_op, env)
    write_fast_cli_report(empty_no_op, 'run-empty-no-op', 'task-empty-no-op', 'fix specified typo in README', tests_status='not_applicable')
    capture_baseline(empty_no_op, 'run-empty-no-op', 'task-empty-no-op', env, text='fix specified typo in README', task_type='docs')
    write_fast_optimistic_report(empty_no_op, 'run-empty-no-op', 'task-empty-no-op', changed_files=[], final_message='nothing to change')
    compare_baseline(empty_no_op, 'run-empty-no-op', 'task-empty-no-op', env)
    proc = run_may_fail([sys.executable, str(ROOT / 'scripts' / 'check_delivery_outcome.py'), '--workspace', str(empty_no_op), '--run-id', 'run-empty-no-op', '--task-id', 'task-empty-no-op'], ROOT, env)
    assert proc.returncode == 1
    empty_no_op_outcome = read_json(empty_no_op / '.zoo-agent' / 'runs' / 'run-empty-no-op' / 'delivery-outcome.json')
    assert empty_no_op_outcome['delivery_outcome'] == 'no_delivery'

    dirty = unique_dir('agent-dirty-readiness-alpha')
    init_repo(dirty, env)
    write(dirty / 'README.md', '# Dirty\n')
    run_may_fail(
        [sys.executable, str(ROOT / 'scripts' / 'check_project_readiness.py'), '--workspace', str(dirty), '--output', str(dirty / '.zoo-agent' / 'project-readiness.json')],
        ROOT,
        env,
    )
    dirty_readiness = read_json(dirty / '.zoo-agent' / 'project-readiness.json')
    assert 'dirty_worktree' in blocker_types(dirty_readiness)

    unborn = unique_dir('agent-unborn-readiness-alpha')
    run(['git', 'init'], unborn, env)
    write(unborn / 'README.md', '# Unborn\n')
    run_may_fail(
        [sys.executable, str(ROOT / 'scripts' / 'check_project_readiness.py'), '--workspace', str(unborn), '--output', str(unborn / '.zoo-agent' / 'project-readiness.json')],
        ROOT,
        env,
    )
    unborn_readiness = read_json(unborn / '.zoo-agent' / 'project-readiness.json')
    assert 'unborn_repo' in blocker_types(unborn_readiness)

    nested = unique_dir('agent-nested-readiness-alpha')
    init_repo(nested, env)
    run(['git', 'init', 'RULES'], nested, env)
    run_may_fail(
        [sys.executable, str(ROOT / 'scripts' / 'check_project_readiness.py'), '--workspace', str(nested), '--output', str(nested / '.zoo-agent' / 'project-readiness.json')],
        ROOT,
        env,
    )
    nested_readiness = read_json(nested / '.zoo-agent' / 'project-readiness.json')
    assert 'nested_git_repo' in blocker_types(nested_readiness)

    unborn_bootstrap = unique_dir('agent-unborn-bootstrap-alpha')
    run(['git', 'init'], unborn_bootstrap, env)
    write(unborn_bootstrap / 'README.md', '# No auto commit\n')
    run_may_fail([AGENT, 'bootstrap', '--workspace', str(unborn_bootstrap)], unborn_bootstrap, env)
    assert run_may_fail(['git', 'rev-parse', '--verify', 'HEAD'], unborn_bootstrap, env).returncode != 0
    cached = run_may_fail(['git', 'diff', '--cached', '--name-only'], unborn_bootstrap, env)
    assert not cached.stdout.strip(), 'bootstrap must not stage files with git add all'

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
    for metric in ['fast_path_pre_backend_overhead_ms', 'backend_execution_ms', 'total_wall_time_ms']:
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
