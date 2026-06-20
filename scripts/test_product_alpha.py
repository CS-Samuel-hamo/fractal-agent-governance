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


def run(cmd: list[str], cwd: Path, *, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
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
    return json.loads(proc.stdout)


def init_repo(env: dict[str, str]) -> Path:
    base = Path(tempfile.gettempdir())
    repo = Path(tempfile.mkdtemp(prefix='product-alpha-', dir=str(base))).resolve()
    (repo / 'README.md').write_text('# Product Alpha\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'product-alpha@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Product Alpha'], repo, env=env)
    run(['git', 'add', 'README.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def assert_no_internal_leak(text: str) -> None:
    forbidden = [
        '"planner"',
        '"executor"',
        '"verifier"',
        'scheduler_control',
        'goal_state_management',
        'goal_state_manager',
        'runtime_status.py',
        'execution_result',
    ]
    for item in forbidden:
        assert item not in text, f'product output leaked internal term: {item}'


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='product-alpha-codex-home-')).resolve()))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)

    for required in ['README.md', 'INSTALL.md', 'QUICKSTART.md', 'EXAMPLES.md', 'ARCHITECTURE.md', 'CLI_REFERENCE.md', 'BACKEND_PLUGINS.md', 'docs/product-mind-model.md']:
        assert (ROOT / required).exists(), f'missing product document: {required}'

    version = run([sys.executable, str(AGENT), '--version'], ROOT, env=env).stdout
    assert '0.8.5' in version

    help_text = run([sys.executable, str(AGENT), '--help'], ROOT, env=env).stdout
    for visible in ['run', 'pipeline', 'goal', 'status', 'backend']:
        assert visible in help_text
    for hidden in ['planner', 'executor', 'verifier', 'codex-health']:
        assert hidden not in help_text

    repo = init_repo(env)
    run([sys.executable, str(AGENT), 'bootstrap', '--workspace', str(repo)], repo, env=env)

    backend_list = payload(run([sys.executable, str(AGENT), 'backend', 'list', '--workspace', str(repo)], repo, env=env))
    assert backend_list['status'] == 'ok'
    assert {'mock', 'dry_run', 'codex'}.issubset(set(backend_list['available_backends']))

    switched = payload(run([sys.executable, str(AGENT), 'backend', 'switch', 'mock', '--workspace', str(repo)], repo, env=env))
    assert switched == {'status': 'ok', 'selected_backend': 'mock', 'result': 'backend switched'}

    goal = payload(run([sys.executable, str(AGENT), 'goal', 'make README onboarding clear', '--workspace', str(repo)], repo, env=env))
    assert goal == {'goal': 'make README onboarding clear', 'progress': 'active', 'result': 'goal set'}

    result1_proc = run(
        [
            sys.executable,
            str(AGENT),
            'run',
            'add a short README note',
            '--workspace',
            str(repo),
            '--run-id',
            'product-alpha-run',
            '--allowed-file',
            'README.md',
            '--dry-run',
        ],
        repo,
        env=env,
    )
    assert_no_internal_leak(result1_proc.stdout)
    result1 = payload(result1_proc)
    assert result1 == {'goal': 'add a short README note', 'progress': 'complete', 'result': 'DRY_RUN_COMPLETE'}

    execution = json.loads((repo / '.zoo-agent' / 'runs' / 'product-alpha-run' / 'pipeline' / 'execution_result.json').read_text(encoding='utf-8'))
    leaf = execution['leaf_results'][0]
    assert leaf['backend_type'] == 'mock'
    assert not any(key.startswith('codex_') for key in leaf)

    result2_proc = run(
        [
            sys.executable,
            str(AGENT),
            'pipeline',
            'add a short README note',
            '--workspace',
            str(repo),
            '--run-id',
            'product-alpha-pipeline',
            '--allowed-file',
            'README.md',
            '--dry-run',
        ],
        repo,
        env=env,
    )
    assert_no_internal_leak(result2_proc.stdout)
    result2 = payload(result2_proc)
    assert result2 == {'goal': 'add a short README note', 'progress': 'complete', 'result': 'DRY_RUN_COMPLETE'}

    status = run([sys.executable, str(AGENT), 'status', '--workspace', str(repo), '--no-write'], repo, env=env)
    assert status.returncode == 0
    assert_no_internal_leak(status.stdout)
    status_payload = payload(status)
    assert sorted(status_payload) == ['goal', 'progress', 'result']

    print('product alpha tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
