#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import pipeline_executor  # noqa: E402
from execution_health_scoring import score_execution_health  # noqa: E402
from execution_result_model import build_execution_result_model  # noqa: E402


def run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode:
        raise AssertionError(proc.stdout)


def temp_repo() -> Path:
    base = Path(tempfile.gettempdir())
    repo = Path(tempfile.mkdtemp(prefix='execution-resilience-', dir=str(base))).resolve()
    (repo / 'README.md').write_text('# Demo\n\nInitial.\n', encoding='utf-8')
    (repo / 'src').mkdir()
    (repo / 'tests').mkdir()
    (repo / 'src' / 'app.py').write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')
    (repo / 'tests' / 'test_app.py').write_text('from src.app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'execution@example.local'], repo)
    run(['git', 'config', 'user.name', 'Execution Resilience Test'], repo)
    run(['git', 'add', '.'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    return repo


def write_plan(repo: Path, run_id: str, objective: str, allowed: list[str]) -> Path:
    plan_dir = repo / '.zoo-agent' / 'runs' / run_id / 'pipeline'
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan = {
        'schema_version': '1.0',
        'generated_by': 'test_execution_resilience.py',
        'stage': 'planner',
        'run_id': run_id,
        'workspace': str(repo),
        'input': objective,
        'execution_plan': {'route': 'fast', 'mode': 'actual_allowed'},
        'decomposition': {
            'leaf_tasks': [
                {
                    'leaf_id': 'leaf-001',
                    'objective': objective,
                    'task_type': 'code',
                    'risk_level': 'low',
                    'allowed_files': allowed,
                    'denied_files': ['.env', '.env.*'],
                    'acceptance': [objective],
                    'preferred_route': 'fast',
                    'execution_mode': 'actual_allowed',
                    'resolution': 'execute',
                }
            ]
        },
    }
    path = plan_dir / 'plan.json'
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def execute_with_fake(plan: Path, fake: Callable[..., dict[str, Any]], *, max_retries: int = 2) -> dict[str, Any]:
    original = pipeline_executor.run_backend_leaf

    def fake_backend(**kwargs: Any) -> dict[str, Any]:
        return fake(
            workspace=kwargs['workspace'],
            task_dir=kwargs['task_dir'],
            sandbox=kwargs['sandbox'],
            timeout_seconds=kwargs['timeout_seconds'],
            dry_run=kwargs['dry_run'],
        )

    pipeline_executor.run_backend_leaf = fake_backend
    try:
        args = argparse.Namespace(
            plan=str(plan),
            workspace='.',
            run_id='',
            output='',
            dry_run=False,
            allow_actual=True,
            sandbox='workspace-write',
            timeout_seconds=120,
            max_retries=max_retries,
            backend='mock',
        )
        return pipeline_executor.execute_plan(args)
    finally:
        pipeline_executor.run_backend_leaf = original


def test_timeout_retry_success() -> None:
    repo = temp_repo()
    plan = write_plan(repo, 'retry-success', 'append a line to README.md', ['README.md'])
    calls = {'count': 0}

    def fake(*, workspace: Path, task_dir: Path, sandbox: str, timeout_seconds: int, dry_run: bool) -> dict[str, Any]:
        calls['count'] += 1
        if calls['count'] == 1:
            return {'returncode': 124, 'stdout_tail': '{"status":"timeout","returncode":124}', 'stderr_tail': '', 'duration_seconds': 120.0}
        (workspace / 'README.md').write_text('# Demo\n\nInitial.\n\nRetry delivered.\n', encoding='utf-8')
        return {'returncode': 0, 'stdout_tail': '{"status":"succeeded","returncode":0}', 'stderr_tail': '', 'duration_seconds': 1.0}

    result = execute_with_fake(plan, fake)
    leaf = result['leaf_results'][0]
    assert calls['count'] == 2
    assert leaf['delivery_outcome'] == 'delivered'
    assert leaf['execution_model']['execution_status'] == 'success'
    assert leaf['retry_count'] == 1


def test_partial_execution_detection() -> None:
    repo = temp_repo()
    plan = write_plan(repo, 'partial', 'add multiply and test', ['src/app.py', 'tests/test_app.py'])

    def fake(*, workspace: Path, task_dir: Path, sandbox: str, timeout_seconds: int, dry_run: bool) -> dict[str, Any]:
        (workspace / 'src' / 'app.py').write_text('def add(a, b):\n    return a + b\n\n\ndef multiply(a, b):\n    return a * b\n', encoding='utf-8')
        return {'returncode': 0, 'stdout_tail': '{"status":"succeeded","returncode":0}', 'stderr_tail': '', 'duration_seconds': 1.0}

    result = execute_with_fake(plan, fake, max_retries=0)
    leaf = result['leaf_results'][0]
    assert leaf['execution_model']['execution_status'] == 'partial'
    assert leaf['delivery_outcome'] == 'dry_run_only'
    assert 'dry_run_mode' in leaf['fallback_history']


def test_fallback_chain_activation() -> None:
    repo = temp_repo()
    plan = write_plan(repo, 'fallback', 'append a line to README.md', ['README.md'])

    def fake(*, workspace: Path, task_dir: Path, sandbox: str, timeout_seconds: int, dry_run: bool) -> dict[str, Any]:
        return {'returncode': 124, 'stdout_tail': '{"status":"timeout","returncode":124}', 'stderr_tail': '', 'duration_seconds': 120.0}

    result = execute_with_fake(plan, fake, max_retries=1)
    leaf = result['leaf_results'][0]
    assert leaf['delivery_outcome'] == 'dry_run_only'
    assert 'split_execution' in leaf['fallback_history']
    assert 'dry_run_mode' in leaf['fallback_history']


def test_execution_split_success() -> None:
    repo = temp_repo()
    plan = write_plan(repo, 'split-success', 'update code and test', ['src/app.py', 'tests/test_app.py'])
    calls = {'count': 0}

    def fake(*, workspace: Path, task_dir: Path, sandbox: str, timeout_seconds: int, dry_run: bool) -> dict[str, Any]:
        calls['count'] += 1
        prompt = (task_dir / 'CODEX_TASK_PROMPT.md').read_text(encoding='utf-8')
        if calls['count'] == 1:
            return {'returncode': 124, 'stdout_tail': '{"status":"timeout","returncode":124}', 'stderr_tail': '', 'duration_seconds': 120.0}
        if 'src/app.py' in prompt:
            (workspace / 'src' / 'app.py').write_text('def add(a, b):\n    return a + b\n\n\ndef multiply(a, b):\n    return a * b\n', encoding='utf-8')
        if 'tests/test_app.py' in prompt:
            (workspace / 'tests' / 'test_app.py').write_text('from src.app import add, multiply\n\n\ndef test_add():\n    assert add(1, 2) == 3\n\n\ndef test_multiply():\n    assert multiply(2, 3) == 6\n', encoding='utf-8')
        return {'returncode': 0, 'stdout_tail': '{"status":"succeeded","returncode":0}', 'stderr_tail': '', 'duration_seconds': 1.0}

    result = execute_with_fake(plan, fake, max_retries=0)
    leaf = result['leaf_results'][0]
    assert leaf['delivery_outcome'] == 'delivered'
    assert leaf['fallback_used'] == 'split_execution'
    assert set(leaf['business_changed_files']) == {'src/app.py', 'tests/test_app.py'}


def test_health_scoring_downgrade() -> None:
    score = score_execution_health(
        [
            {'execution_status': 'timeout', 'confidence': 0.1, 'execution_time': 120},
            {'execution_status': 'partial', 'confidence': 0.4, 'execution_time': 20},
        ]
    )
    assert score['score'] < 0.5
    assert score['parallel_allowed'] is False


def test_returncode_zero_no_diff_not_success() -> None:
    model = build_execution_result_model(task_id='leaf-001', backend_returncode=0, worker_status='succeeded', business_changed_files=[])
    assert model['execution_status'] == 'failed'
    assert model['reason'] == 'returncode_zero_without_business_diff'


def main() -> int:
    test_timeout_retry_success()
    test_partial_execution_detection()
    test_fallback_chain_activation()
    test_execution_split_success()
    test_health_scoring_downgrade()
    test_returncode_zero_no_diff_not_success()
    print('execution resilience tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
