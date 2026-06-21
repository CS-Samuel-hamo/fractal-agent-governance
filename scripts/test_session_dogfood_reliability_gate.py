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

from session_reliability_gate import evaluate_trace  # noqa: E402


AGENT = ROOT / 'scripts' / 'agent.py'


def run(command: list[str], cwd: Path, *, allow_fail: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='session-dogfood-codex-home-')).resolve()))
    proc = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0 and not allow_fail:
        raise AssertionError(f'command failed: {command}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def workspace() -> Path:
    return Path(tempfile.mkdtemp(prefix='session-dogfood-gate-', dir=tempfile.gettempdir())).resolve()


def require_complete_dogfood(root: Path) -> dict[str, Any]:
    run([sys.executable, str(ROOT / 'scripts' / 'session_dogfood_runner.py'), '--workspace', str(root)], root)
    base = root / '.zoo-agent' / 'session_dogfood'
    trace = load(base / 'session_dogfood_trace.json')
    report = load(base / 'session_reliability_report.json')
    readiness = load(base / 'readiness_for_096.json')
    assert len(trace.get('runs') or []) == 6
    scenarios = {item['scenario']: item for item in trace['runs']}
    for scenario in ['normal_session', 'undo', 'resume', 'needs_attention', 'no_delivery', 'budget']:
        assert scenarios[scenario]['scenario_result'] == 'pass', scenario
    assert report['recommendation'] == 'pass'
    assert readiness['readiness'] == 'READY_FOR_096_MULTI_BACKEND_ROUTER'
    assert (base / 'session_replay.md').exists()
    assert (base / 'session_product_report.md').exists()
    return trace


def first_actual_step(trace: dict[str, Any]) -> dict[str, Any]:
    for run_row in trace.get('runs') or []:
        for step in run_row.get('steps') or []:
            if step.get('execution_outcome') in {'delivered', 'no_delivery', 'paused'} and run_row.get('scenario') != 'budget':
                return step
    raise AssertionError('no actual-like step found')


def assert_negative_cases(trace: dict[str, Any]) -> None:
    missing_checkpoint = copy.deepcopy(trace)
    first_actual_step(missing_checkpoint)['checkpoint_created'] = False
    missing_report = evaluate_trace(missing_checkpoint)
    assert 'missing_checkpoint_before_execution' in missing_report['failed_checks']
    assert missing_report['recommendation'] in {'fix_before_096', 'fail'}

    non_map = copy.deepcopy(trace)
    first_actual_step(non_map)['selected_action_source'] = 'manual'
    non_map_report = evaluate_trace(non_map)
    assert 'non_map_backed_action_detected' in non_map_report['failed_checks']
    assert non_map_report['map_backed_execution_score'] < 1.0

    leakage = copy.deepcopy(trace)
    first_actual_step(leakage)['command'] = 'planner debug output'
    leakage_report = evaluate_trace(leakage)
    assert leakage_report['internal_leakage_detected'] is True
    assert leakage_report['recommendation'] == 'fail'

    unsafe = copy.deepcopy(trace)
    first_actual_step(unsafe)['command'] = 'git push origin main'
    unsafe_report = evaluate_trace(unsafe)
    assert unsafe_report['unsafe_behavior_detected'] is True
    assert unsafe_report['recommendation'] == 'fail'


def assert_agent_entrypoint(root: Path) -> None:
    help_text = run([sys.executable, str(AGENT), '--help'], root).stdout.lower()
    assert 'agent start "<project goal>"' in help_text
    assert 'session --dogfood' not in help_text
    assert '--dogfood' not in help_text

    proc = run([sys.executable, str(AGENT), 'session', '--dogfood', '--workspace', str(root)], root)
    payload = json.loads(proc.stdout)
    assert payload['task'] == 'session dogfood'
    assert 'READY_FOR_096_MULTI_BACKEND_ROUTER' in payload['result']
    assert 'session_product_report.md' in payload['result']


def main() -> int:
    root = workspace()
    trace = require_complete_dogfood(root)
    assert_negative_cases(trace)
    assert_agent_entrypoint(root)
    print('session dogfood reliability gate tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
