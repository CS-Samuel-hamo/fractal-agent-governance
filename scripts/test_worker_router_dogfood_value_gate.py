#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from worker_router_value_gate import evaluate_worker_router_value

AGENT = ROOT / 'scripts' / 'agent.py'


def run(command: list[str], cwd: Path, *, allow_fail: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='worker-dogfood-test-codex-home-')).resolve()))
    proc = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    if proc.returncode != 0 and not allow_fail:
        raise AssertionError(f'command failed: {command}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def workspace() -> Path:
    return Path(tempfile.mkdtemp(prefix='worker-router-dogfood-', dir=tempfile.gettempdir())).resolve()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def run_complete_dogfood(root: Path) -> dict[str, Any]:
    run([sys.executable, str(ROOT / 'scripts' / 'worker_router_dogfood_runner.py'), '--workspace', str(root)], root)
    base = root / '.zoo-agent' / 'worker_dogfood'
    trace = load(base / 'worker_router_dogfood_trace.json')
    value = load(base / 'worker_router_value_report.json')
    readiness = load(base / 'readiness_for_0962.json')
    scenarios = {item['scenario']: item for item in trace['runs']}
    for scenario in [
        'docs_update',
        'repo_scan',
        'test_update',
        'small_code_edit',
        'blocked_zone',
        'degraded_worker',
        'all_actual_workers_unavailable',
        'session_integration',
    ]:
        assert scenario in scenarios, scenario
        assert scenarios[scenario]['outcome'] == 'pass', scenario
    assert value['recommendation'] == 'pass'
    assert readiness['readiness'] == 'READY_FOR_0962_REAL_WORKER_ADAPTER_HARDENING'
    assert (base / 'worker_router_replay.md').exists()
    assert (base / 'worker_router_product_report.md').exists()
    return trace


def first_run(trace: dict[str, Any], scenario: str) -> dict[str, Any]:
    for row in trace.get('runs') or []:
        if row.get('scenario') == scenario:
            return row
    raise AssertionError(f'missing scenario {scenario}')


def assert_negative_cases(trace: dict[str, Any]) -> None:
    unavailable_actual = copy.deepcopy(trace)
    row = first_run(unavailable_actual, 'docs_update')
    row['routing_decision']['selected_worker'] = 'claude_worker_stub'
    row['routing_decision']['execution_mode'] = 'auto'
    row['routing_decision']['execution_allowed'] = True
    row['selected_worker_available'] = False
    report = evaluate_worker_router_value(unavailable_actual)
    assert report['recommendation'] == 'fail'
    assert any('unavailable_worker_actual' in item for item in report['failed_checks'])

    fake_capability = copy.deepcopy(trace)
    for worker in fake_capability['registry_snapshot']['workers']:
        if worker['name'] == 'claude_worker_stub':
            worker['available'] = True
            worker['supports_actual_execution'] = True
    fake_report = evaluate_worker_router_value(fake_capability)
    assert fake_report['fake_capability_detected'] is True
    assert fake_report['recommendation'] == 'fail'

    blocked_breakout = copy.deepcopy(trace)
    blocked = first_run(blocked_breakout, 'blocked_zone')
    blocked['routing_decision']['execution_allowed'] = True
    blocked['routing_decision']['execution_mode'] = 'auto'
    blocked_report = evaluate_worker_router_value(blocked_breakout)
    assert blocked_report['unsafe_behavior_detected'] is True
    assert any('blocked_zone_executed' in item for item in blocked_report['failed_checks'])

    provider_hardcode = copy.deepcopy(trace)
    route = first_run(provider_hardcode, 'docs_update')
    route['routing_basis'] = ['provider_name']
    route['routing_decision']['routing_reason'] = 'provider_hardcode:codex'
    provider_report = evaluate_worker_router_value(provider_hardcode)
    assert provider_report['recommendation'] == 'fix_before_0962'
    assert any('provider_hardcode' in item for item in provider_report['failed_checks'])


def assert_agent_entrypoint(root: Path) -> None:
    help_text = run([sys.executable, str(AGENT), '--help'], root).stdout.lower()
    assert 'workers --dogfood' not in help_text
    assert 'agent workers' not in help_text
    proc = run([sys.executable, str(AGENT), 'workers', '--dogfood', '--workspace', str(root)], root)
    payload = json.loads(proc.stdout)
    assert payload['task'] == 'workers dogfood'
    assert 'READY_FOR_0962_REAL_WORKER_ADAPTER_HARDENING' in payload['result']
    assert 'worker_router_product_report.md' in payload['result']


def main() -> int:
    root = workspace()
    trace = run_complete_dogfood(root)
    assert_negative_cases(trace)
    assert_agent_entrypoint(root)
    print('worker router dogfood value gate tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
