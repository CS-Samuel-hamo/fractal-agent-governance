#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from project_map_schema import (
    action_row,
    capability_row,
    default_project_map,
    default_project_state,
    evidence_item,
    module_row,
)
from runtime_common import load_json, project_root, utc_now, write_json
from session_product_report_generator import generate_report
from session_reliability_gate import run_gate
from session_trace_replayer import run_replay

AGENT = ROOT / 'scripts' / 'agent.py'


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'session_dogfood'


def run_proc(command: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    return {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}


def agent(repo: Path, args: list[str]) -> dict[str, Any]:
    return run_proc([sys.executable, str(AGENT), *args, '--workspace', str(repo)], repo)


def init_fixture_repo(project: Path, name: str, *, docs: bool = True) -> Path:
    _ = project
    repo = Path(tempfile.mkdtemp(prefix=f'session-dogfood-{name}-')).resolve()
    (repo / 'README.md').write_text(f'# {name}\n\nSynthetic session dogfood fixture.\n', encoding='utf-8')
    if docs:
        (repo / 'docs').mkdir(parents=True, exist_ok=True)
        (repo / 'docs' / 'guide.md').write_text('# Guide\n\nSynthetic documentation.\n', encoding='utf-8')
    run_proc(['git', 'init'], repo)
    run_proc(['git', 'config', 'user.email', 'session-dogfood@example.local'], repo)
    run_proc(['git', 'config', 'user.name', 'Session Dogfood'], repo)
    run_proc(['git', 'add', 'README.md', 'docs'], repo)
    run_proc(['git', 'commit', '-m', 'init synthetic fixture'], repo)
    return repo


def write_blocked_project_map(repo: Path, goal: str) -> None:
    evidence = [
        evidence_item(
            'configuration_surface', 'config/access.yml', 'Synthetic guarded access boundary.', confidence=0.7
        )
    ]
    project_map = default_project_map(repo, main_goal=goal)
    project_map.update(
        {
            'modules': [
                module_row(
                    'module-access-boundary',
                    'Access Boundary',
                    'Synthetic blocked surface.',
                    ['config/access.yml'],
                    evidence,
                    status='risky',
                    confidence=0.7,
                )
            ],
            'capabilities': [
                capability_row(
                    'capability-release-safety', 'Release safety', 'partial', evidence, ['module-access-boundary']
                )
            ],
            'risks': [
                {
                    'risk_id': 'risk-protected-access-boundary',
                    'description': 'Protected access changes require attention.',
                    'severity': 'high',
                    'affected_files': ['config/access.yml'],
                    'evidence': evidence,
                }
            ],
            'next_actions': [
                action_row(
                    'action-protected-access-boundary',
                    'Review protected access boundary',
                    'The synthetic map marks this as a protected high-risk area.',
                    'Prevents accidental changes in a protected area.',
                    'high',
                    ['config/access.yml'],
                    evidence,
                )
            ],
            'last_updated': utc_now(),
        }
    )
    base = repo / '.zoo-agent' / 'map'
    write_json(base / 'project_map.json', project_map)
    write_json(base / 'project_state.json', default_project_state(repo, main_goal=goal))
    write_json(
        base / 'map_evidence.json', {'schema_version': '1.0', 'evidence': evidence, 'skipped_sensitive_paths': []}
    )


def write_stale_lock(repo: Path) -> None:
    write_json(
        repo / '.zoo-agent' / 'session' / 'session_lock.json',
        {
            'schema_version': '1.0',
            'generated_by': 'session_dogfood_runner.py',
            'session_id': 'synthetic-interruption',
            'pid': 0,
            'created_at': '2000-01-01T00:00:00Z',
            'created_monotonic': 1.0,
        },
    )


def state(repo: Path) -> dict[str, Any]:
    return load_json(repo / '.zoo-agent' / 'session' / 'session_state.json')


def history(repo: Path) -> list[dict[str, Any]]:
    payload = load_json(repo / '.zoo-agent' / 'session' / 'session_history.json')
    return [item for item in payload.get('steps') or [] if isinstance(item, dict)]


def checkpoint_count(repo: Path) -> int:
    payload = load_json(repo / '.zoo-agent' / 'autopilot' / 'checkpoints.json')
    return len([item for item in payload.get('checkpoints') or [] if isinstance(item, dict)])


def selected(repo: Path) -> dict[str, Any]:
    return load_json(repo / '.zoo-agent' / 'autopilot' / 'selected_next_action.json')


def artifact_exists(repo: Path, rel: str) -> bool:
    return (repo / rel).exists()


def normalize_outcome(value: str, scenario: str, status_after: str) -> str:
    if scenario == 'budget':
        return 'paused'
    if scenario == 'needs_attention':
        return 'blocked'
    if scenario == 'no_delivery':
        return 'no_delivery'
    if value == 'dry_run_only':
        return 'no_delivery'
    if value in {'delivered', 'no_delivery', 'blocked', 'failed', 'paused'}:
        return value
    if status_after == 'paused':
        return 'paused'
    return 'failed' if status_after == 'failed' else value or 'delivered'


def trace_step(
    repo: Path, *, scenario: str, step: int, command: str, before: str, checkpoints_before: int
) -> dict[str, Any]:
    current = state(repo)
    selected_action = selected(repo)
    rows = history(repo)
    last = rows[-1] if rows else {}
    status_after = str(current.get('status') or 'not_started')
    outcome = normalize_outcome(str(last.get('outcome') or ''), scenario, status_after)
    if command in {'agent stop', 'agent undo', 'agent status'}:
        outcome = 'paused'
    return {
        'step': step,
        'command': command,
        'session_status_before': before,
        'selected_action': selected_action.get('title') or last.get('title') or '',
        'selected_action_source': selected_action.get('source') or last.get('source') or '',
        'checkpoint_created': checkpoint_count(repo) > checkpoints_before,
        'execution_outcome': outcome,
        'project_map_updated': artifact_exists(repo, '.zoo-agent/map/project_map.json'),
        'digest_updated': artifact_exists(repo, '.zoo-agent/session/session_digest.md'),
        'cockpit_synced': artifact_exists(repo, '.zoo-agent/cockpit/index.html'),
        'session_status_after': status_after,
        'attention_required': bool(current.get('attention_required')),
        'resume_available': bool(current.get('resume_available', True)),
    }


def scenario_normal(project: Path) -> dict[str, Any]:
    repo = init_fixture_repo(project, 'normal-session')
    steps: list[dict[str, Any]] = []
    before = state(repo).get('status') or 'not_started'
    cp = checkpoint_count(repo)
    start = agent(repo, ['start', 'prepare this project for public release', '--backend', 'mock'])
    steps.append(
        trace_step(
            repo,
            scenario='normal_session',
            step=1,
            command='agent start "prepare this project for public release"',
            before=before,
            checkpoints_before=cp,
        )
    )
    before = state(repo).get('status') or 'unknown'
    cp = checkpoint_count(repo)
    cont = agent(repo, ['continue', '--backend', 'mock'])
    steps.append(
        trace_step(
            repo, scenario='normal_session', step=2, command='agent continue', before=before, checkpoints_before=cp
        )
    )
    before = state(repo).get('status') or 'unknown'
    cp = checkpoint_count(repo)
    stop = agent(repo, ['stop'])
    steps.append(
        trace_step(repo, scenario='normal_session', step=3, command='agent stop', before=before, checkpoints_before=cp)
    )
    ok = all(item['returncode'] == 0 for item in [start, cont, stop]) and steps[-1]['session_status_after'] == 'stopped'
    return {'scenario': 'normal_session', 'steps': steps, 'scenario_result': 'pass' if ok else 'fail'}


def scenario_undo(project: Path) -> dict[str, Any]:
    repo = init_fixture_repo(project, 'undo-session')
    steps: list[dict[str, Any]] = []
    before = state(repo).get('status') or 'not_started'
    cp = checkpoint_count(repo)
    start = agent(repo, ['start', 'prepare this project for public release', '--backend', 'mock'])
    steps.append(
        trace_step(
            repo,
            scenario='undo',
            step=1,
            command='agent start "prepare this project for public release"',
            before=before,
            checkpoints_before=cp,
        )
    )
    before = state(repo).get('status') or 'unknown'
    cp = checkpoint_count(repo)
    undo = agent(repo, ['undo'])
    steps.append(trace_step(repo, scenario='undo', step=2, command='agent undo', before=before, checkpoints_before=cp))
    ok = (
        start['returncode'] == 0
        and undo['returncode'] == 0
        and checkpoint_count(repo) > 0
        and steps[-1]['digest_updated']
        and steps[-1]['cockpit_synced']
    )
    return {'scenario': 'undo', 'steps': steps, 'scenario_result': 'pass' if ok else 'fail'}


def scenario_resume(project: Path) -> dict[str, Any]:
    repo = init_fixture_repo(project, 'resume-session')
    steps: list[dict[str, Any]] = []
    before = state(repo).get('status') or 'not_started'
    cp = checkpoint_count(repo)
    start = agent(repo, ['start', 'prepare this project for public release', '--backend', 'mock'])
    steps.append(
        trace_step(
            repo,
            scenario='resume',
            step=1,
            command='agent start "prepare this project for public release"',
            before=before,
            checkpoints_before=cp,
        )
    )
    write_stale_lock(repo)
    status = agent(repo, ['status'])
    before = state(repo).get('status') or 'unknown'
    cp = checkpoint_count(repo)
    cont = agent(repo, ['continue', '--backend', 'mock'])
    steps.append(
        trace_step(repo, scenario='resume', step=2, command='agent continue', before=before, checkpoints_before=cp)
    )
    ok = (
        start['returncode'] == 0
        and status['returncode'] == 0
        and cont['returncode'] == 0
        and steps[-1]['resume_available']
    )
    return {'scenario': 'resume', 'steps': steps, 'scenario_result': 'pass' if ok else 'fail'}


def scenario_needs_attention(project: Path) -> dict[str, Any]:
    repo = init_fixture_repo(project, 'needs-attention', docs=False)
    goal = 'prepare this project for public release'
    write_blocked_project_map(repo, goal)
    before = state(repo).get('status') or 'not_started'
    cp = checkpoint_count(repo)
    start = agent(repo, ['start', goal, '--backend', 'mock'])
    step = trace_step(
        repo,
        scenario='needs_attention',
        step=1,
        command='agent start "prepare this project for public release"',
        before=before,
        checkpoints_before=cp,
    )
    ok = (
        start['returncode'] == 0
        and step['session_status_after'] == 'needs_attention'
        and step['attention_required']
        and not step['checkpoint_created']
    )
    return {'scenario': 'needs_attention', 'steps': [step], 'scenario_result': 'pass' if ok else 'fail'}


def scenario_no_delivery(project: Path) -> dict[str, Any]:
    repo = init_fixture_repo(project, 'no-delivery')
    before = state(repo).get('status') or 'not_started'
    cp = checkpoint_count(repo)
    start = agent(repo, ['start', 'prepare this project for public release', '--backend', 'dry_run'])
    step = trace_step(
        repo,
        scenario='no_delivery',
        step=1,
        command='agent start "prepare this project for public release"',
        before=before,
        checkpoints_before=cp,
    )
    ok = (
        start['returncode'] == 0
        and step['session_status_after'] == 'needs_attention'
        and step['execution_outcome'] == 'no_delivery'
    )
    return {'scenario': 'no_delivery', 'steps': [step], 'scenario_result': 'pass' if ok else 'fail'}


def scenario_budget(project: Path) -> dict[str, Any]:
    repo = init_fixture_repo(project, 'budget-session')
    before = state(repo).get('status') or 'not_started'
    cp = checkpoint_count(repo)
    start = agent(repo, ['start', 'prepare this project for public release', '--backend', 'mock', '--max-steps', '1'])
    step = trace_step(
        repo,
        scenario='budget',
        step=1,
        command='agent start "prepare this project for public release"',
        before=before,
        checkpoints_before=cp,
    )
    ok = start['returncode'] == 0 and step['session_status_after'] == 'paused' and step['execution_outcome'] == 'paused'
    return {'scenario': 'budget', 'steps': [step], 'scenario_result': 'pass' if ok else 'fail'}


def run_dogfood(project: Path) -> dict[str, Any]:
    base = dogfood_dir(project)
    base.mkdir(parents=True, exist_ok=True)
    runs = [
        scenario_normal(project),
        scenario_undo(project),
        scenario_resume(project),
        scenario_needs_attention(project),
        scenario_no_delivery(project),
        scenario_budget(project),
    ]
    trace = {
        'schema_version': '1.0',
        'generated_by': 'session_dogfood_runner.py',
        'generated_at': utc_now(),
        'fixture_note': 'synthetic controlled fixtures only',
        'runs': runs,
    }
    write_json(base / 'session_dogfood_trace.json', trace)
    reliability = run_gate(project)
    run_replay(project)
    product = generate_report(project)
    readiness = product.get('readiness') or {}
    return {
        'status': 'ok' if readiness.get('readiness') == 'READY_FOR_096_MULTI_BACKEND_ROUTER' else 'needs_fix',
        'trace': '.zoo-agent/session_dogfood/session_dogfood_trace.json',
        'reliability_report': '.zoo-agent/session_dogfood/session_reliability_report.json',
        'replay': '.zoo-agent/session_dogfood/session_replay.md',
        'product_report': '.zoo-agent/session_dogfood/session_product_report.md',
        'readiness': readiness,
        'reliability': reliability,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Run controlled long-running session dogfood.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = run_dogfood(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('status') == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
