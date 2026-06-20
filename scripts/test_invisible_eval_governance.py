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


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def init_repo(env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix='invisible-eval-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Invisible Eval\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'invisible@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Invisible Eval Test'], repo, env=env)
    run(['git', 'add', 'README.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def test_hidden_eval_after_public_preview(env: dict[str, str]) -> None:
    repo = init_repo(env)
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo, env=env)
    proc = run(
        [sys.executable, str(AGENT), 'fix README typo', '--workspace', str(repo), '-f', 'README.md'],
        repo,
        env=env,
    )
    output = proc.stdout.lower()
    public_payload = json.loads(proc.stdout)
    assert sorted(public_payload) == ['mode', 'result', 'task']
    for hidden in ['eval', 'governance', 'learning', 'curator', 'runtime_health']:
        assert hidden not in output

    invisible_eval = load(repo / '.zoo-agent' / 'eval' / 'invisible_eval.json')
    assert invisible_eval['run_id']
    assert 0.0 <= float(invisible_eval['execution_quality_score']) <= 1.0
    assert 0.0 <= float(invisible_eval['success_confidence']) <= 1.0
    assert invisible_eval['failure_type'] in {'none', 'timeout', 'partial', 'no_delivery', 'wrong_output'}
    assert invisible_eval['recommended_internal_action'] in {'none', 'retry', 'fallback', 'split', 'escalate'}
    assert invisible_eval['recommended_internal_action'] == 'none'

    health = load(repo / '.zoo-agent' / 'eval' / 'runtime_health.json')
    metrics = health['metrics']
    for metric in [
        'eval_accuracy_score',
        'false_success_detection_rate',
        'failure_classification_accuracy',
        'fallback_effectiveness',
        'runtime_stability_score',
        'backend_behavior_consistency',
    ]:
        assert metric in metrics
        assert 0.0 <= float(metrics[metric]) <= 1.0

    learning = load(repo / '.zoo-agent' / 'learning' / 'signals.json')
    assert learning['signals']


def test_false_success_detection(env: dict[str, str]) -> None:
    repo = init_repo(env)
    run_id = 'synthetic-false-success'
    base = repo / '.zoo-agent' / 'runs' / run_id / 'pipeline'
    plan = {
        'run_id': run_id,
        'execution_plan': {'route': 'fast'},
    }
    execution = {
        'run_id': run_id,
        'stage': 'executor',
        'leaf_results': [
            {
                'leaf_id': 'leaf-001',
                'delivery_outcome': 'no_delivery',
                'backend_status': 'succeeded',
                'execution_model': {
                    'execution_status': 'failed',
                    'confidence': 0.25,
                    'backend_returncode': 0,
                    'output_diff': [],
                },
            }
        ],
    }
    final = {
        'run_id': run_id,
        'final_verdict': 'COMPLETED',
        'goal_converged': True,
    }
    write(base / 'plan.json', plan)
    write(base / 'execution_result.json', execution)
    write(base / 'final_result.json', final)
    proc = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'invisible_eval_engine.py'),
            '--workspace',
            str(repo),
            '--run-id',
            run_id,
            '--plan',
            str(base / 'plan.json'),
            '--execution-result',
            str(base / 'execution_result.json'),
            '--final-result',
            str(base / 'final_result.json'),
        ],
        repo,
        env=env,
    )
    assert json.loads(proc.stdout)['status'] == 'ok'
    payload = load(repo / '.zoo-agent' / 'eval' / 'invisible_eval.json')
    assert payload['false_success_detected'] is True
    assert payload['failure_type'] == 'no_delivery'
    assert payload['recommended_internal_action'] in {'fallback', 'escalate'}


def test_timeout_governance_and_learning(env: dict[str, str]) -> None:
    repo = init_repo(env)
    run_id = 'synthetic-timeout'
    base = repo / '.zoo-agent' / 'runs' / run_id / 'pipeline'
    write(base / 'plan.json', {'run_id': run_id, 'execution_plan': {'route': 'fast'}})
    write(
        base / 'execution_result.json',
        {
            'run_id': run_id,
            'stage': 'executor',
            'leaf_results': [
                {
                    'leaf_id': 'leaf-001',
                    'delivery_outcome': 'blocked',
                    'backend_status': 'timeout',
                    'execution_model': {'execution_status': 'timeout', 'confidence': 0.1, 'backend_returncode': 124},
                }
            ],
        },
    )
    write(base / 'final_result.json', {'run_id': run_id, 'final_verdict': 'BLOCKED', 'goal_converged': False})
    run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'invisible_eval_engine.py'),
            '--workspace',
            str(repo),
            '--run-id',
            run_id,
            '--plan',
            str(base / 'plan.json'),
            '--execution-result',
            str(base / 'execution_result.json'),
            '--final-result',
            str(base / 'final_result.json'),
        ],
        repo,
        env=env,
    )
    payload = load(repo / '.zoo-agent' / 'eval' / 'invisible_eval.json')
    assert payload['failure_type'] == 'timeout'
    assert payload['recommended_internal_action'] in {'retry', 'fallback'}
    signals = load(repo / '.zoo-agent' / 'learning' / 'signals.json')['signals']
    assert any('timeout' in item.get('pattern_tags', []) for item in signals)


def test_no_new_public_cli_surface(env: dict[str, str]) -> None:
    help_text = run([sys.executable, str(AGENT), '--help'], ROOT, env=env).stdout.lower()
    for hidden in ['eval', 'governance', 'learning', 'curator']:
        assert hidden not in help_text


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='invisible-eval-codex-home-')).resolve()))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)
    test_hidden_eval_after_public_preview(env)
    test_false_success_detection(env)
    test_timeout_governance_and_learning(env)
    test_no_new_public_cli_surface(env)
    print('invisible eval governance tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
