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

import pipeline_executor
from explanation_engine import build_execution_explanation
from runtime_common import write_json
from safety_summary_generator import build_safety_summary
from trust_score_engine import build_trust_score


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def init_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix='decision-control-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Decision Control\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'decision@example.local'], repo)
    run(['git', 'config', 'user.name', 'Decision Control Test'], repo)
    run(['git', 'add', 'README.md'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    return repo


def plan_for(repo: Path, risk_level: str, run_id: str) -> Path:
    path = repo / '.zoo-agent' / 'runs' / run_id / 'pipeline' / 'plan.json'
    payload = {
        'schema_version': '1.0',
        'generated_by': 'test_decision_control_layer.py',
        'run_id': run_id,
        'workspace': str(repo),
        'goal': 'append a harmless README line',
        'execution_plan': {'mode': 'actual_allowed', 'route': 'fast'},
        'decomposition': {
            'leaf_tasks': [
                {
                    'leaf_id': 'leaf-001',
                    'objective': 'append a harmless README line',
                    'resolution': 'execute',
                    'risk_level': risk_level,
                    'execution_mode': 'actual_allowed',
                    'preferred_route': 'fast',
                    'allowed_files': ['README.md'],
                    'denied_files': ['.env', 'secrets/**'],
                    'acceptance': ['README.md contains the added line.'],
                }
            ]
        },
    }
    write_json(path, payload)
    return path


def execute_plan(plan_path: Path, repo: Path) -> dict:
    args = argparse.Namespace(
        plan=str(plan_path),
        workspace=str(repo),
        run_id='',
        output='',
        dry_run=False,
        allow_actual=True,
        sandbox='workspace-write',
        backend='mock',
        backend_option=[],
        timeout_seconds=60,
        max_retries=0,
    )
    return pipeline_executor.execute_plan(args)


def assert_advisory_payload(payload: dict) -> None:
    assert payload['safe_to_apply'] == 'suggested_only'
    assert payload['requires_user_confirmation'] is True
    assert payload['recommendation'] in {'proceed', 'review', 'avoid'}
    assert payload['risk_level'] in {'low', 'medium', 'high'}
    assert payload['reasoning']


def test_advisory_schema(repo: Path) -> None:
    eval_payload = {
        'run_id': 'decision-advisory',
        'execution_quality_score': 1.0,
        'backend_behavior_score': 1.0,
        'false_success_detected': False,
        'failure_type': 'none',
    }
    impact = {
        'affected_files': ['README.md'],
        'affected_modules': ['docs'],
        'cross_module_risk': 'medium',
        'backward_compatibility': 'compatible',
        'rollback_cost': 'medium',
    }
    trust = build_trust_score(repo, eval_payload, impact)
    explanation = build_execution_explanation(
        plan={'goal': 'append a README note', 'decomposition': {'leaf_tasks': []}},
        execution={'run_id': 'decision-advisory', 'leaf_results': []},
        final_result={'run_id': 'decision-advisory', 'final_verdict': 'COMPLETED'},
        impact=impact,
        trust=trust,
    )
    safety = build_safety_summary(
        explanation, impact, trust, {'run_id': 'decision-advisory', 'final_verdict': 'COMPLETED'}
    )
    assert_advisory_payload(trust)
    assert_advisory_payload(explanation)
    assert_advisory_payload(safety)
    assert 'safe_to_deploy' not in safety


def test_risky_leaf_never_auto_applies(repo: Path) -> None:
    original_readme = (repo / 'README.md').read_text(encoding='utf-8')
    plan = plan_for(repo, 'medium', 'decision-medium-risk')
    result = execute_plan(plan, repo)
    leaf = result['leaf_results'][0]
    assert result['execution_backend']['invoked'] is False
    assert leaf['backend_invoked'] is False
    assert leaf['delivery_outcome'] == 'blocked'
    assert leaf['result'] == 'user_confirmation_required'
    assert leaf['decision_control']['safe_to_apply'] == 'suggested_only'
    assert leaf['decision_control']['recommendation'] == 'review'
    assert '[CONFIRM REQUIRED]' in leaf['confirmation_prompt']
    assert (repo / 'README.md').read_text(encoding='utf-8') == original_readme


def test_trust_cannot_bypass_execution_gate(repo: Path) -> None:
    plan = plan_for(repo, 'high', 'decision-high-trust')
    plan_payload = load(plan)
    plan_payload['trust_score'] = 1.0
    plan_payload['safe_to_apply'] = 'suggested_only'
    write_json(plan, plan_payload)
    result = execute_plan(plan, repo)
    leaf = result['leaf_results'][0]
    assert result['execution_backend']['invoked'] is False
    assert leaf['backend_status'] == 'not_invoked_confirmation_required'
    assert leaf['decision_control']['recommendation'] == 'avoid'
    assert leaf['decision_control']['requires_user_confirmation'] is True


def test_low_risk_apply_still_requires_explicit_action(repo: Path) -> None:
    plan = plan_for(repo, 'low', 'decision-low-risk')
    result = execute_plan(plan, repo)
    leaf = result['leaf_results'][0]
    assert result['execution_backend']['invoked'] is True
    assert leaf['backend_invoked'] is True
    assert leaf['requires_user_confirmation'] is True
    assert leaf['user_confirmation_source'] == '--apply'
    assert leaf['decision_control']['safe_to_apply'] == 'suggested_only'
    assert 'Mock backend delivered.' in (repo / 'README.md').read_text(encoding='utf-8')


def main() -> int:
    repo = init_repo()
    test_advisory_schema(repo)
    test_risky_leaf_never_auto_applies(repo)
    test_trust_cannot_bypass_execution_gate(repo)
    test_low_risk_apply_still_requires_explicit_action(repo)
    print('decision control layer tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
