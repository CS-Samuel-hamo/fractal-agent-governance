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

from real_worker_value_gate import evaluate_real_worker_value  # noqa: E402


AGENT = ROOT / 'scripts' / 'agent.py'


def run(command: list[str], cwd: Path, *, allow_fail: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='real-worker-test-codex-home-')).resolve()))
    proc = subprocess.run(command, cwd=cwd, env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0 and not allow_fail:
        raise AssertionError(f'command failed: {command}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def workspace() -> Path:
    return Path(tempfile.mkdtemp(prefix='real-worker-dogfood-test-', dir=tempfile.gettempdir())).resolve()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def run_complete(root: Path) -> dict[str, Any]:
    run([sys.executable, str(ROOT / 'scripts' / 'real_worker_dogfood_runner.py'), '--workspace', str(root)], root)
    base = root / '.zoo-agent' / 'real_worker_dogfood'
    trace = load(base / 'real_worker_dogfood_trace.json')
    value = load(base / 'real_worker_value_report.json')
    readiness = load(base / 'readiness_for_097.json')
    scenarios = {item['scenario']: item for item in trace.get('runs') or []}
    for scenario in [
        'worker_doctor',
        'local_scanner_repo_scan',
        'project_map_support',
        'session_with_real_worker_availability',
        'codex_unavailable_graceful_degrade',
        'claude_detection_no_fake_actual',
        'cockpit_worker_readiness',
    ]:
        assert scenario in scenarios, scenario
        assert scenarios[scenario]['outcome'] == 'pass', scenario
    assert value['recommendation'] == 'pass'
    assert readiness['readiness'] == 'READY_FOR_097_CROSS_PROJECT_LEARNING'
    assert (base / 'real_worker_replay.md').exists()
    assert (base / 'project_operator_value_report.md').exists()
    return trace


def artifacts(root: Path) -> dict[str, Any]:
    cockpit = root / '.zoo-agent' / 'cockpit' / 'index.html'
    env = root / '.zoo-agent' / 'workers' / 'worker_environment_report.md'
    return {
        'doctor': load(root / '.zoo-agent' / 'workers' / 'worker_doctor_report.json'),
        'environment_report': env.read_text(encoding='utf-8', errors='replace'),
        'scanner_report': load(root / '.zoo-agent' / 'workers' / 'local_scanner_report.json'),
        'codex_health': load(root / '.zoo-agent' / 'workers' / 'codex_adapter_health.json'),
        'claude_detection': load(root / '.zoo-agent' / 'workers' / 'claude_code_detection.json'),
        'registry': load(root / '.zoo-agent' / 'workers' / 'worker_registry.json'),
        'routing_decision': load(root / '.zoo-agent' / 'workers' / 'routing_decision.json'),
        'cockpit_html': cockpit.read_text(encoding='utf-8', errors='replace'),
        'project_map': load(root / '.zoo-agent' / 'map' / 'project_map.json'),
        'map_evidence': load(root / '.zoo-agent' / 'map' / 'map_evidence.json'),
    }


def evaluate(trace: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    return evaluate_real_worker_value(trace, **pack)


def assert_negative_cases(trace: dict[str, Any], pack: dict[str, Any]) -> None:
    fake_pack = copy.deepcopy(pack)
    for worker in fake_pack['registry']['workers']:
        if worker['name'] == 'claude_worker_stub':
            worker['supports_actual_execution'] = True
    fake_report = evaluate(trace, fake_pack)
    assert fake_report['fake_capability_detected'] is True
    assert fake_report['recommendation'] == 'fail'

    secret_pack = copy.deepcopy(pack)
    secret_pack['scanner_report']['leaked'] = 'should-not-be-read'
    secret_report = evaluate(trace, secret_pack)
    assert secret_report['secret_read_detected'] is True
    assert secret_report['recommendation'] == 'fail'

    internal_pack = copy.deepcopy(pack)
    internal_pack['environment_report'] += '\nscheduler internal trace\n'
    internal_report = evaluate(trace, internal_pack)
    assert internal_report['internal_leakage_detected'] is True
    assert internal_report['recommendation'] == 'fail'

    fatal_trace = copy.deepcopy(trace)
    for row in fatal_trace['runs']:
        if row['scenario'] == 'codex_unavailable_graceful_degrade':
            row['worker_environment']['codex'] = 'fatal'
            row['outcome'] = 'fail'
    fatal_report = evaluate(fatal_trace, pack)
    assert any('codex_fatal_behavior_detected' in item for item in fatal_report['failed_checks'])
    assert fatal_report['recommendation'] == 'fix_before_097'


def assert_agent_entrypoint(root: Path) -> None:
    help_text = run([sys.executable, str(AGENT), '--help'], root).stdout.lower()
    assert 'workers --real-dogfood' not in help_text
    assert 'agent workers' not in help_text
    proc = run([sys.executable, str(AGENT), 'workers', '--real-dogfood', '--workspace', str(root)], root)
    payload = json.loads(proc.stdout)
    assert payload['task'] == 'real worker dogfood'
    assert 'READY_FOR_097_CROSS_PROJECT_LEARNING' in payload['result']
    assert 'project_operator_value_report.md' in payload['result']


def main() -> int:
    root = workspace()
    trace = run_complete(root)
    pack = artifacts(root)
    assert_negative_cases(trace, pack)
    assert_agent_entrypoint(root)
    print('real worker adapter dogfood tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
