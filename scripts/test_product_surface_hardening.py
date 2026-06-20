#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'

ABSOLUTE_PATH_RE = re.compile(r'[A-Za-z]:[\\/]')
DEFAULT_FORBIDDEN = [
    'goal_state_manager',
    'runtime_status.py',
    'global_loop_state',
    'loop_state',
    'scheduler',
    'planner',
    'executor',
    'verifier',
    'aggregation',
    'execution_result',
    'backend internal',
]
DOC_FORBIDDEN = [
    'goal_state_manager',
    'runtime_status.py',
    'global_loop_state',
    'loop_state',
    'scheduler',
    'planner',
    'executor',
    'verifier',
    'aggregation',
]


def run(cmd: list[str], cwd: Path, *, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
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


def payload(proc: subprocess.CompletedProcess[str]) -> dict:
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f'expected JSON product output, got: {proc.stdout}') from exc


def assert_product_payload(text: str) -> dict:
    assert not ABSOLUTE_PATH_RE.search(text), f'absolute path leaked in product output: {text}'
    lowered = text.lower()
    for term in DEFAULT_FORBIDDEN:
        assert term not in lowered, f'internal runtime term leaked in product output: {term}'
    parsed = payload(type('Completed', (), {'stdout': text})())
    assert sorted(parsed) == ['goal', 'progress', 'result'], parsed
    return parsed


def init_repo(env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix='product-surface-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Product Surface\n\nInitial text.\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'surface@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Product Surface Test'], repo, env=env)
    run(['git', 'add', 'README.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def assert_docs_clean() -> None:
    for rel in ['README.md', 'INSTALL.md', 'QUICKSTART.md', 'EXAMPLES.md', 'CLI_REFERENCE.md', 'BACKEND_PLUGINS.md', 'ARCHITECTURE.md', 'docs/product-mind-model.md']:
        text = (ROOT / rel).read_text(encoding='utf-8')
        assert '.py' not in text, f'{rel} exposes script file paths'
        assert not ABSOLUTE_PATH_RE.search(text), f'{rel} exposes a local absolute path'
        lowered = text.lower()
        for term in DOC_FORBIDDEN:
            assert term not in lowered, f'{rel} exposes internal term: {term}'


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='product-surface-codex-home-')).resolve()))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)

    assert_docs_clean()
    repo = init_repo(env)

    no_bootstrap_run = run(
        [
            sys.executable,
            str(AGENT),
            'run',
            'fix README typo',
            '--workspace',
            str(repo),
            '--run-id',
            'surface-no-bootstrap',
            '--allowed-file',
            'README.md',
            '--dry-run',
        ],
        repo,
        env=env,
    )
    assert_product_payload(no_bootstrap_run.stdout)

    bootstrap = run([sys.executable, str(AGENT), 'bootstrap', '--workspace', str(repo)], repo, env=env)
    assert_product_payload(bootstrap.stdout)

    run([sys.executable, str(AGENT), 'backend', 'switch', 'mock', '--workspace', str(repo)], repo, env=env)
    goal = run([sys.executable, str(AGENT), 'goal', 'make README onboarding clear', '--workspace', str(repo)], repo, env=env)
    assert_product_payload(goal.stdout)

    status = run([sys.executable, str(AGENT), 'status', '--workspace', str(repo), '--no-write'], repo, env=env)
    assert_product_payload(status.stdout)

    run_result = run(
        [
            sys.executable,
            str(AGENT),
            'run',
            'add a short README note',
            '--workspace',
            str(repo),
            '--run-id',
            'surface-run',
            '--allowed-file',
            'README.md',
            '--dry-run',
        ],
        repo,
        env=env,
    )
    assert_product_payload(run_result.stdout)

    pipeline_result = run(
        [
            sys.executable,
            str(AGENT),
            'pipeline',
            'add a short README note',
            '--workspace',
            str(repo),
            '--run-id',
            'surface-pipeline',
            '--allowed-file',
            'README.md',
            '--dry-run',
        ],
        repo,
        env=env,
    )
    assert_product_payload(pipeline_result.stdout)

    rollback_result = run(
        [
            sys.executable,
            str(AGENT),
            'rollback',
            '--workspace',
            str(repo),
            '--run-id',
            'surface-missing-run',
            '--task-id',
            'surface-missing-task',
            '--dry-run',
        ],
        repo,
        env=env,
    )
    assert_product_payload(rollback_result.stdout)

    for typo in ['rum', 'runn']:
        typo_result = run([sys.executable, str(AGENT), typo], repo, env=env, check=False)
        assert typo_result.returncode != 0
        assert_product_payload(typo_result.stdout)
        assert 'try: agent run' in typo_result.stdout

    empty_goal = run([sys.executable, str(AGENT), 'goal', ''], repo, env=env, check=False)
    assert empty_goal.returncode != 0
    assert_product_payload(empty_goal.stdout)
    assert 'missing goal' in empty_goal.stdout

    wrong_backend = run([sys.executable, str(AGENT), 'backend', 'switch', 'not-real', '--workspace', str(repo)], repo, env=env, check=False)
    assert wrong_backend.returncode != 0
    assert not ABSOLUTE_PATH_RE.search(wrong_backend.stdout)
    assert 'unknown backend' in wrong_backend.stdout

    debug_status = run([sys.executable, str(AGENT), 'status', '--workspace', str(repo), '--no-write', '--debug'], repo, env=env)
    assert any(term in debug_status.stdout for term in ['runtime_status.py', 'goal_state', 'loop_state'])

    debug_run = run(
        [
            sys.executable,
            str(AGENT),
            'run',
            'add a short README note',
            '--workspace',
            str(repo),
            '--run-id',
            'surface-debug-run',
            '--allowed-file',
            'README.md',
            '--dry-run',
            '--debug',
        ],
        repo,
        env=env,
    )
    assert any(term in debug_run.stdout for term in ['stages', 'pipeline_loop.py'])

    print('product surface hardening tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
