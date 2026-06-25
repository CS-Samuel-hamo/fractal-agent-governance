#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from route_task import backend_actual_allowed
from runtime_common import utc_now, write_json


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if check and proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def repo() -> Path:
    base = Path(tempfile.gettempdir())
    path = Path(tempfile.mkdtemp(prefix='backend-health-gate-', dir=str(base))).resolve()
    (path / 'README.md').write_text('# Backend Health Gate\n', encoding='utf-8')
    run(['git', 'init'], path)
    return path


def write_profile(path: Path, health_status: str, *, allow_fast: bool = True, allow_parallel: bool = True) -> None:
    write_json(
        path / '.zoo-agent' / 'backend' / 'codex-backend-profile.json',
        {
            'schema_version': '1.0',
            'health_status': health_status,
            'last_health_check_at': utc_now(),
            'health_ttl_minutes': 60,
            'recommended_usage': {
                'allow_fast_actual': allow_fast,
                'allow_parallel_actual': allow_parallel,
                'allow_governed_actual': False,
            },
        },
    )


def test_healthy_allows_fast_and_parallel() -> None:
    path = repo()
    goal = {'goal_id': 'production', 'goal': 'Improve README for users', 'goal_type': 'production_goal'}
    classification = {'path': 'fast', 'task_scale': 'small', 'signals': {'hard_risk_hits': []}}
    write_profile(path, 'healthy')
    fast_allowed, fast_profile = backend_actual_allowed(
        path, selected_path='fast', goal=goal, classification=classification
    )
    parallel_allowed, parallel_profile = backend_actual_allowed(
        path, require_parallel=True, selected_path='parallel', goal=goal, classification=classification
    )
    assert fast_allowed is True
    assert fast_profile['execution_gate']['reason'] == 'healthy_backend_actual_allowed'
    assert parallel_allowed is True
    assert parallel_profile['execution_gate']['reason'] == 'healthy_backend_parallel_allowed'


def test_warnings_allow_single_fast_but_block_parallel() -> None:
    path = repo()
    goal = {'goal_id': 'production', 'goal': 'Improve README for users', 'goal_type': 'production_goal'}
    classification = {'path': 'fast', 'task_scale': 'small', 'signals': {'hard_risk_hits': []}}
    write_profile(path, 'healthy_with_warnings', allow_parallel=False)
    fast_allowed, fast_profile = backend_actual_allowed(
        path, selected_path='fast', goal=goal, classification=classification
    )
    parallel_allowed, parallel_profile = backend_actual_allowed(
        path, require_parallel=True, selected_path='parallel', goal=goal, classification=classification
    )
    assert fast_allowed is True
    assert fast_profile['execution_gate']['reason'] == 'healthy_with_warnings_single_low_risk_fast_allowed'
    assert parallel_allowed is False
    assert parallel_profile['execution_gate']['reason'] == 'parallel_requires_healthy_backend'


def test_unhealthy_blocks_all_actual_and_diagnostic_blocks_actual() -> None:
    path = repo()
    prod = {'goal_id': 'production', 'goal': 'Improve README for users', 'goal_type': 'production_goal'}
    diagnostic = {
        'goal_id': 'diagnostic',
        'goal': 'Controlled diagnostic dry-run validation test',
        'goal_type': 'diagnostic_goal',
    }
    classification = {'path': 'fast', 'task_scale': 'small', 'signals': {'hard_risk_hits': []}}
    write_profile(path, 'unhealthy')
    allowed, profile = backend_actual_allowed(path, selected_path='fast', goal=prod, classification=classification)
    assert allowed is False
    assert profile['execution_gate']['reason'] == 'backend_unhealthy_blocks_actual_execution'
    write_profile(path, 'healthy')
    diagnostic_allowed, diagnostic_profile = backend_actual_allowed(
        path, selected_path='fast', goal=diagnostic, classification=classification
    )
    assert diagnostic_allowed is False
    assert diagnostic_profile['execution_gate']['reason'] == 'diagnostic_goal_dry_run_only'


def test_health_script_outputs_gate_policy() -> None:
    path = repo()
    proc = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'check_codex_backend_health.py'),
            '--workspace',
            str(path),
            '--mode',
            'quick',
            '--skip-real-codex',
        ],
        path,
        check=False,
    )
    assert proc.returncode in {0, 20}
    health_path = path / '.zoo-agent' / 'backend' / 'codex-health-quick.json'
    payload = json.loads(health_path.read_text(encoding='utf-8-sig'))
    assert 'execution_gate' in payload
    assert 'allowed_modes' in payload['execution_gate']


def main() -> int:
    os.environ.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='agent-runtime-codex-home-')).resolve()))
    test_healthy_allows_fast_and_parallel()
    test_warnings_allow_single_fast_but_block_parallel()
    test_unhealthy_blocks_all_actual_and_diagnostic_blocks_actual()
    test_health_script_outputs_gate_policy()
    print('backend health gate tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
