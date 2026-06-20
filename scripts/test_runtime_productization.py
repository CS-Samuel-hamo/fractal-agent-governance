#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from backend_registry import default_registry  # noqa: E402
from runtime_core import RuntimeCore  # noqa: E402
from runtime_common import write_json  # noqa: E402


def run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode:
        raise AssertionError(proc.stdout)
    return proc.stdout


def temp_repo(prefix: str) -> Path:
    base = Path('D:/AI_DEV/temp') if Path('D:/AI_DEV/temp').exists() else Path(tempfile.gettempdir())
    repo = Path(tempfile.mkdtemp(prefix=prefix, dir=str(base))).resolve()
    (repo / 'README.md').write_text('# Runtime Productization\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'runtime@example.local'], repo)
    run(['git', 'config', 'user.name', 'Runtime Productization Test'], repo)
    run(['git', 'add', '.'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    return repo


def current_execution_result(payload: dict) -> dict:
    iterations = (payload.get('result') or {}).get('iterations') or []
    assert iterations, payload
    execution_ref = iterations[-1].get('execution_result_ref')
    if not execution_ref:
        execution_ref = str(Path((payload.get('result') or {}).get('final_result_ref', '')).parent / 'execution_result.json')
    return json.loads(Path(execution_ref).read_text(encoding='utf-8-sig'))


def test_backend_registry_contract() -> None:
    registry = default_registry()
    names = registry.names()
    assert {'codex', 'mock', 'dry_run'}.issubset(set(names))
    for name in ['mock', 'dry_run']:
        backend = registry.get(name)
        assert backend.health()['available'] is True
        assert callable(getattr(backend, 'execute'))


def test_runtime_pipeline_with_mock_backend() -> None:
    repo = temp_repo('runtime-product-mock-')
    core = RuntimeCore(repo, backend='mock')
    result = core.run_goal(
        'Update README with a product runtime marker.',
        run_id='runtime-mock',
        dry_run=False,
        allow_actual=True,
        allowed_files=['README.md'],
    )
    assert result['status'] == 'ok'
    execution = current_execution_result(result['pipeline'])
    assert execution['execution_backend']['selected'] == 'mock'
    assert execution['execution_backend']['invoked'] is True
    leaf = execution['leaf_results'][0]
    assert leaf['delivery_outcome'] == 'delivered'
    assert leaf['backend'] == 'mock'
    assert 'codex_invoked' not in leaf
    assert 'Mock backend delivered.' in (repo / 'README.md').read_text(encoding='utf-8')


def test_backend_failure_does_not_crash_runtime() -> None:
    repo = temp_repo('runtime-product-failure-')
    plan_dir = repo / '.zoo-agent' / 'runs' / 'runtime-failure' / 'pipeline'
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan = {
        'schema_version': '1.0',
        'generated_by': 'test_runtime_productization.py',
        'stage': 'planner',
        'run_id': 'runtime-failure',
        'workspace': str(repo),
        'input': 'fail through mock backend',
        'execution_plan': {'route': 'fast', 'mode': 'actual_allowed'},
        'decomposition': {
            'leaf_tasks': [
                {
                    'leaf_id': 'leaf-001',
                    'objective': 'fail through mock backend',
                    'task_type': 'docs',
                    'risk_level': 'low',
                    'allowed_files': ['README.md'],
                    'denied_files': ['.env'],
                    'acceptance': ['Failure must be contained by runtime.'],
                    'preferred_route': 'fast',
                    'execution_mode': 'actual_allowed',
                    'resolution': 'execute',
                    'mock_mode': 'failure',
                }
            ]
        },
    }
    plan_path = plan_dir / 'plan.json'
    write_json(plan_path, plan)
    output = plan_dir / 'execution_result.json'
    stdout = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'pipeline_executor.py'),
            '--plan',
            str(plan_path),
            '--output',
            str(output),
            '--backend',
            'mock',
            '--allow-actual',
            '--max-retries',
            '0',
        ],
        ROOT,
    )
    assert '"status": "ok"' in stdout
    execution = json.loads(output.read_text(encoding='utf-8-sig'))
    leaf = execution['leaf_results'][0]
    assert leaf['delivery_outcome'] == 'dry_run_only'
    assert leaf['result'] == 'fallback_dry_run_after_execution_failure'
    assert execution['execution_backend']['selected'] == 'mock'


def test_switch_backend_and_status() -> None:
    repo = temp_repo('runtime-product-switch-')
    core = RuntimeCore(repo)
    switched = core.switch_backend('mock')
    assert switched['status'] == 'ok'
    status = core.get_status()
    assert status['backend'] == 'mock'
    assert status['backend_selection'] == 'mock'
    paused = core.pause()
    resumed = core.resume()
    assert paused['status'] == 'paused'
    assert resumed['status'] == 'active'


def main() -> int:
    test_backend_registry_contract()
    test_runtime_pipeline_with_mock_backend()
    test_backend_failure_does_not_crash_runtime()
    test_switch_backend_and_status()
    print('runtime productization tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
