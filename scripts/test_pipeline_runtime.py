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


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
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
    if check and proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def temp_repo() -> Path:
    base = Path('D:/AI_DEV/temp') if Path('D:/AI_DEV/temp').exists() else Path(tempfile.gettempdir())
    repo = Path(tempfile.mkdtemp(prefix='pipeline-runtime-', dir=str(base))).resolve()
    (repo / 'README.md').write_text('# Pipeline Runtime\n\nInitial text.\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    (repo / 'src').mkdir()
    (repo / 'src' / 'example.py').write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'pipeline@example.local'], repo)
    run(['git', 'config', 'user.name', 'Pipeline Runtime Test'], repo)
    run(['git', 'add', '.'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    (repo / '.zoo-agent').mkdir()
    (repo / '.zoo-agent' / 'bootstrap.lock').write_text('test bootstrap marker\n', encoding='utf-8')
    return repo


def set_goal(repo: Path) -> dict:
    run(
        [
            sys.executable,
            str(AGENT),
            'goal',
            'set',
            'Improve README onboarding wording only.',
            '--workspace',
            str(repo),
            '--goal-id',
            'pipeline-goal',
            '--priority',
            '80',
            '--resource',
            'README.md',
            '--success-criteria',
            'README wording is reviewable.',
            '--non-goal',
            'Do not modify runtime behavior.',
        ],
        repo,
    )
    return load(repo / '.zoo-agent' / 'goal' / 'goal_state.json')


def pipeline_dir(repo: Path, run_id: str) -> Path:
    return repo / '.zoo-agent' / 'runs' / run_id / 'pipeline'


def test_stage_contracts() -> None:
    repo = temp_repo()
    before_state = set_goal(repo)
    run_id = 'pipeline-contracts'
    out_dir = pipeline_dir(repo, run_id)
    plan = out_dir / 'plan.json'
    execution = out_dir / 'execution_result.json'
    final = out_dir / 'final_result.json'

    run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'pipeline_planner.py'),
            'fix README wording only',
            '--workspace',
            str(repo),
            '--run-id',
            run_id,
            '--goal-id',
            'pipeline-goal',
            '--allowed-file',
            'README.md',
            '--output',
            str(plan),
            '--dry-run',
        ],
        repo,
    )
    assert plan.exists()
    assert sorted(path.name for path in out_dir.iterdir()) == ['plan.json']
    plan_payload = load(plan)
    assert plan_payload['stage'] == 'planner'
    assert plan_payload['execution_plan']['executor_contract'] == 'executor_reads_plan_json_only'

    run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'pipeline_executor.py'),
            '--plan',
            str(plan),
            '--output',
            str(execution),
            '--dry-run',
        ],
        repo,
    )
    assert execution.exists()
    execution_payload = load(execution)
    assert execution_payload['stage'] == 'executor'
    assert execution_payload['scheduler_used'] is False
    assert execution_payload['conflict_detector_used'] is False
    assert execution_payload['aggregation_used'] is False
    assert execution_payload['execution_backend']['replaceable'] is True
    assert execution_payload['execution_backend']['invoked'] is False
    assert 'codex_backend' not in execution_payload

    run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'pipeline_verifier.py'),
            '--execution-result',
            str(execution),
            '--output',
            str(final),
        ],
        repo,
    )
    final_payload = load(final)
    assert final_payload['stage'] == 'verifier'
    assert final_payload['backend_invoked'] is False
    assert 'codex_invoked' not in final_payload
    assert final_payload['planner_invoked'] is False
    assert final_payload['executor_invoked'] is False
    assert final_payload['checks']['scheduler_not_used_by_executor'] is True
    assert final_payload['checks']['aggregation_not_used_by_executor'] is True

    after_state = load(repo / '.zoo-agent' / 'goal' / 'goal_state.json')
    assert after_state == before_state


def test_simple_pipeline_loop() -> None:
    repo = temp_repo()
    set_goal(repo)
    run_id = 'pipeline-loop'
    proc = run(
        [
            sys.executable,
            str(AGENT),
            'pipeline',
            'fix README wording only',
            '--workspace',
            str(repo),
            '--run-id',
            run_id,
            '--goal-id',
            'pipeline-goal',
            '--allowed-file',
            'README.md',
            '--dry-run',
        ],
        repo,
    )
    report = json.loads(proc.stdout)
    assert report['status'] == 'ok'
    assert report['run']['run_id'] == run_id
    assert report['result']['verdict'] == 'DRY_RUN_COMPLETE'
    assert 'stages' not in report
    internal = load(pipeline_dir(repo, run_id) / 'pipeline-loop.json')
    assert internal['stages'] == ['planner', 'executor', 'verifier']
    assert internal['multi_layer_loop'] is False
    assert internal['scheduler_control'] is False
    assert internal['goal_state_management'] is False
    assert internal['iterations'][0]['stages']['planner']['returncode'] == 0
    assert internal['iterations'][0]['stages']['executor']['returncode'] == 0
    assert internal['iterations'][0]['stages']['verifier']['returncode'] == 0
    final = load(pipeline_dir(repo, run_id) / 'final_result.json')
    assert final['final_verdict'] == 'DRY_RUN_COMPLETE'


def main() -> int:
    os.environ.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='pipeline-codex-home-')).resolve()))
    test_stage_contracts()
    test_simple_pipeline_loop()
    print('pipeline runtime tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
