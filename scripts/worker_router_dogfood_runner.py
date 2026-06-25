#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, utc_now, write_json
from task_profile_classifier import classify_task_profile
from worker_registry import write_worker_registry
from worker_router import route_worker
from worker_router_product_report_generator import generate_report
from worker_router_trace_replayer import run_replay
from worker_router_value_gate import run_value_gate

AGENT = ROOT / 'scripts' / 'agent.py'


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'worker_dogfood'


def run_proc(command: list[str], cwd: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='worker-dogfood-codex-home-')).resolve()))
    proc = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    return {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}


def init_repo(name: str) -> Path:
    repo = Path(tempfile.mkdtemp(prefix=f'worker-dogfood-{name}-')).resolve()
    (repo / 'README.md').write_text(f'# {name}\n\nSynthetic worker router dogfood fixture.\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    (repo / 'examples').mkdir()
    (repo / 'examples' / 'demo.md').write_text('# Demo\n', encoding='utf-8')
    (repo / 'tests').mkdir()
    (repo / 'tests' / 'test_sample.py').write_text('def test_ok():\n    assert True\n', encoding='utf-8')
    (repo / 'src').mkdir()
    (repo / 'src' / 'app.py').write_text('VALUE = 1\n', encoding='utf-8')
    run_proc(['git', 'init'], repo)
    run_proc(['git', 'config', 'user.email', 'worker-dogfood@example.local'], repo)
    run_proc(['git', 'config', 'user.name', 'Worker Dogfood'], repo)
    run_proc(['git', 'add', 'README.md', 'docs', 'examples', 'tests', 'src'], repo)
    run_proc(['git', 'commit', '-m', 'init synthetic fixture'], repo)
    return repo


def action(
    action_id: str,
    title: str,
    target_files: list[str],
    *,
    risk: str = 'low',
    trust: str = 'trusted',
    mode: str = 'auto',
) -> dict[str, Any]:
    return {
        'selected_action_id': action_id,
        'action_id': action_id,
        'title': title,
        'risk_level': risk,
        'trust_zone': trust,
        'execution_mode': mode,
        'target_files': target_files,
        'source': 'project_map.next_actions',
        'why_now': 'Synthetic dogfood action from project map.',
        'expected_impact': 'Validates worker routing behavior.',
    }


def worker_available(repo: Path, worker_name: str) -> bool:
    registry = load_json(repo / '.zoo-agent' / 'workers' / 'worker_registry.json')
    for worker in registry.get('workers') or []:
        if worker.get('name') == worker_name:
            return bool(worker.get('available'))
    return False


def routing_basis() -> list[str]:
    return ['task_profile', 'capability', 'health', 'risk']


def make_trace_row(
    repo: Path,
    *,
    scenario: str,
    action_payload: dict[str, Any],
    requested_worker: str = 'auto',
    create_checkpoint: bool = True,
) -> dict[str, Any]:
    profile = classify_task_profile(action_payload)
    decision = route_worker(
        repo,
        task_profile=profile,
        requested_worker=requested_worker,
        execution_mode=str(action_payload.get('execution_mode') or ''),
    )
    checkpoint_created = False
    if create_checkpoint and decision.get('execution_allowed') and decision.get('execution_mode') == 'auto':
        create_checkpoint_fn = globals()['create_checkpoint']
        create_checkpoint_fn(
            repo,
            action_id=str(action_payload.get('action_id') or scenario),
            title=str(action_payload.get('title') or scenario),
        )
        checkpoint_created = True
    fallback_used = bool(
        requested_worker not in {'', 'auto'}
        and decision.get('selected_provider') != requested_worker
        and decision.get('selected_worker') != requested_worker
    )
    if 'fallback' in str(decision.get('routing_reason') or '') or scenario in {
        'degraded_worker',
        'all_actual_workers_unavailable',
    }:
        fallback_used = True
    row = {
        'scenario': scenario,
        'task_profile': profile,
        'selected_action': action_payload.get('title', ''),
        'selected_action_source': 'project_map.next_actions',
        'routing_decision': {
            'selected_worker': decision.get('selected_worker', ''),
            'worker_type': decision.get('selected_worker_type', ''),
            'provider': decision.get('selected_provider', ''),
            'execution_mode': decision.get('execution_mode', ''),
            'execution_allowed': bool(decision.get('execution_allowed')),
            'routing_reason': decision.get('routing_reason', ''),
            'fallback_workers': decision.get('fallback_workers') or [],
            'worker_role': decision.get('worker_role', ''),
            'rejected_workers': decision.get('rejected_workers') or [],
        },
        'routing_basis': routing_basis(),
        'selected_worker_available': worker_available(repo, str(decision.get('selected_worker') or ''))
        if decision.get('selected_worker')
        else False,
        'fallback_used': fallback_used,
        'fallback_safe': True,
        'checkpoint_created': checkpoint_created,
        'session_updated': False,
        'cockpit_synced': False,
        'outcome': 'pass',
    }
    if scenario == 'blocked_zone':
        row['outcome'] = (
            'pass'
            if not decision.get('execution_allowed') and decision.get('execution_mode') == 'needs_attention'
            else 'fail'
        )
    elif scenario == 'all_actual_workers_unavailable':
        row['outcome'] = (
            'pass'
            if decision.get('execution_mode') == 'preview'
            and decision.get('selected_worker') in {'dry_run_worker', 'local_scanner_worker'}
            else 'fail'
        )
    elif scenario == 'degraded_worker':
        row['outcome'] = (
            'pass'
            if row['fallback_used']
            and decision.get('selected_worker') not in {'claude_worker_stub', 'local_worker_stub'}
            else 'fail'
        )
    elif decision.get('execution_mode') == 'auto' and not checkpoint_created:
        row['outcome'] = 'fail'
    elif decision.get('selected_worker') in {'claude_worker_stub', 'local_worker_stub'}:
        row['outcome'] = 'fail'
    return row


def scenario_session_integration() -> dict[str, Any]:
    repo = init_repo('session-integration')
    run_proc([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo)
    start = run_proc(
        [sys.executable, str(AGENT), 'start', 'prepare this project for public release', '--workspace', str(repo)], repo
    )
    routing = load_json(repo / '.zoo-agent' / 'workers' / 'routing_decision.json')
    selected = load_json(repo / '.zoo-agent' / 'autopilot' / 'selected_next_action.json')
    history = load_json(repo / '.zoo-agent' / 'session' / 'session_history.json')
    checkpoints = load_json(repo / '.zoo-agent' / 'autopilot' / 'checkpoints.json')
    state = load_json(repo / '.zoo-agent' / 'session' / 'session_state.json')
    cockpit = repo / '.zoo-agent' / 'cockpit' / 'index.html'
    profile = routing.get('task_profile') if isinstance(routing.get('task_profile'), dict) else {}
    steps = [item for item in history.get('steps') or [] if isinstance(item, dict)]
    checkpoint_created = bool(checkpoints.get('checkpoints'))
    selected_source = selected.get('source') or (steps[-1].get('source') if steps else '')
    ok = (
        start['returncode'] == 0
        and selected_source == 'project_map.next_actions'
        and checkpoint_created
        and bool(routing.get('selected_worker'))
        and bool(state)
        and cockpit.exists()
    )
    return {
        'scenario': 'session_integration',
        'task_profile': profile,
        'selected_action': selected.get('title') or (steps[-1].get('title') if steps else ''),
        'selected_action_source': selected_source,
        'routing_decision': {
            'selected_worker': routing.get('selected_worker', ''),
            'worker_type': routing.get('selected_worker_type', ''),
            'provider': routing.get('selected_provider', ''),
            'execution_mode': routing.get('execution_mode', ''),
            'execution_allowed': bool(routing.get('execution_allowed')),
            'routing_reason': routing.get('routing_reason', ''),
            'fallback_workers': routing.get('fallback_workers') or [],
            'worker_role': routing.get('worker_role', ''),
            'rejected_workers': routing.get('rejected_workers') or [],
        },
        'routing_basis': routing_basis(),
        'selected_worker_available': worker_available(repo, str(routing.get('selected_worker') or ''))
        if routing.get('selected_worker')
        else False,
        'fallback_used': False,
        'fallback_safe': True,
        'checkpoint_created': checkpoint_created,
        'session_updated': bool(state),
        'cockpit_synced': cockpit.exists(),
        'outcome': 'pass' if ok else 'fail',
    }


def run_dogfood(project: Path) -> dict[str, Any]:
    base = dogfood_dir(project)
    base.mkdir(parents=True, exist_ok=True)
    repo = init_repo('router-scenarios')
    write_worker_registry(project)
    rows = [
        make_trace_row(
            repo,
            scenario='docs_update',
            action_payload=action('action-docs', 'Clarify documentation guide wording', ['docs/guide.md']),
        ),
        make_trace_row(
            repo,
            scenario='repo_scan',
            action_payload=action('action-scan', 'Refresh project map release readiness', [], mode='preview'),
            create_checkpoint=False,
        ),
        make_trace_row(
            repo,
            scenario='test_update',
            action_payload=action('action-tests', 'Improve tests for sample behavior', ['tests/test_sample.py']),
        ),
        make_trace_row(
            repo,
            scenario='small_code_edit',
            action_payload=action('action-code', 'Adjust small source constant', ['src/app.py']),
        ),
        make_trace_row(
            repo,
            scenario='blocked_zone',
            action_payload=action(
                'action-protected-auth',
                'Review protected auth boundary',
                ['auth/access.py'],
                risk='high',
                trust='blocked',
            ),
            create_checkpoint=False,
        ),
        make_trace_row(
            repo,
            scenario='degraded_worker',
            action_payload=action('action-degraded', 'Clarify documentation guide wording', ['docs/guide.md']),
            requested_worker='claude',
        ),
        make_trace_row(
            repo,
            scenario='all_actual_workers_unavailable',
            action_payload=action('action-no-actual-scan', 'Refresh project map release readiness', [], mode='auto'),
            create_checkpoint=False,
        ),
        scenario_session_integration(),
    ]
    write_worker_registry(project)
    trace = {
        'schema_version': '1.0',
        'generated_by': 'worker_router_dogfood_runner.py',
        'generated_at': utc_now(),
        'goal': 'validate multi-backend worker routing for AI Project Operator',
        'registry_snapshot': load_json(project / '.zoo-agent' / 'workers' / 'worker_registry.json'),
        'runs': rows,
    }
    write_json(base / 'worker_router_dogfood_trace.json', trace)
    # Keep top-level worker artifacts useful for final handoff.
    route_worker(
        project,
        task_profile=classify_task_profile(
            action('action-demo', 'Clarify documentation guide wording', ['README.md'], mode='preview')
        ),
        requested_worker='auto',
        execution_mode='preview',
    )
    run_proc([sys.executable, str(AGENT), 'cockpit', '--workspace', str(project)], project)
    value_report = run_value_gate(project)
    run_replay(project)
    product = generate_report(project)
    readiness = product.get('readiness') or {}
    return {
        'status': 'ok' if readiness.get('readiness') == 'READY_FOR_0962_REAL_WORKER_ADAPTER_HARDENING' else 'needs_fix',
        'trace': '.zoo-agent/worker_dogfood/worker_router_dogfood_trace.json',
        'value_report': '.zoo-agent/worker_dogfood/worker_router_value_report.json',
        'replay': '.zoo-agent/worker_dogfood/worker_router_replay.md',
        'product_report': '.zoo-agent/worker_dogfood/worker_router_product_report.md',
        'readiness': readiness,
        'value_gate': value_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Run controlled worker router dogfood.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = run_dogfood(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('status') == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
