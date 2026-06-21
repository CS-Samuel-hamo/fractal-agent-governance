#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from attention_router import mark_attention  # noqa: E402
from checkpoint_manager import create_checkpoint  # noqa: E402
from map_task_selector import select_next_action  # noqa: E402
from progress_summary_generator import build_progress_summary  # noqa: E402
from project_map_builder import build_project_map, render_markdown  # noqa: E402
from project_map_schema import map_dir  # noqa: E402
from project_map_updater import update_project_map  # noqa: E402
from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402
from session_budget_manager import budget_decision, normalize_budget  # noqa: E402
from session_cockpit_sync import sync_cockpit  # noqa: E402
from session_digest_generator import generate_digest  # noqa: E402
from session_failure_policy import classify_step_result  # noqa: E402
from session_state_store import append_session_event, append_session_history, load_session_history, save_session_state  # noqa: E402
from task_profile_classifier import classify_task_profile  # noqa: E402
from worker_execution_adapter import execute_routed_worker  # noqa: E402
from worker_router import route_worker  # noqa: E402


def ensure_project_map(project: Path, goal: str) -> None:
    if (map_dir(project) / 'project_map.json').exists():
        return
    project_map, state, evidence = build_project_map(project, main_goal=goal)
    write_json(map_dir(project) / 'project_map.json', project_map)
    write_json(map_dir(project) / 'project_state.json', state)
    write_json(map_dir(project) / 'map_evidence.json', evidence)
    md = map_dir(project) / 'project_map.md'
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(render_markdown(project_map), encoding='utf-8')


def run_command(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {
        'command': [str(item) for item in command],
        'returncode': proc.returncode,
        'stdout_tail': proc.stdout[-4000:],
        'stderr_tail': proc.stderr[-4000:],
    }


def pipeline_paths(project: Path, run_id: str) -> tuple[Path, Path, Path]:
    base = project / '.zoo-agent' / 'runs' / run_id / 'pipeline'
    return base / 'plan.json', base / 'execution_result.json', base / 'final_result.json'


def execute_action(project: Path, *, action: dict[str, Any], backend: str, step_number: int) -> dict[str, Any]:
    run_id = f'session-{time.strftime("%Y%m%d%H%M%S", time.gmtime())}-{step_number:02d}'
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'pipeline_loop.py'),
        str(action.get('title') or action.get('selected_action_id') or 'project action'),
        '--workspace',
        str(project),
        '--run-id',
        run_id,
        '--max-iterations',
        '1',
        '--backend',
        backend,
        '--max-retries',
        '2',
    ]
    for target in action.get('target_files') or []:
        if target and '*' not in str(target) and not str(target).endswith('/'):
            command.extend(['--allowed-file', str(target)])
    if action.get('execution_mode') == 'auto':
        command.append('--allow-actual')
    else:
        command.append('--dry-run')
    command_result = run_command(command)
    plan_path, execution_path, final_path = pipeline_paths(project, run_id)
    return {
        'run_id': run_id,
        'command_result': command_result,
        'plan_path': str(plan_path),
        'execution_path': str(execution_path),
        'final_path': str(final_path),
        'execution': load_json(execution_path),
        'final_result': load_json(final_path),
    }


def append_autopilot_history(project: Path, row: dict[str, Any]) -> None:
    path = project / '.zoo-agent' / 'autopilot' / 'action_history.json'
    payload = load_json(path)
    rows = [item for item in payload.get('actions') or [] if isinstance(item, dict)]
    rows.append(row)
    write_json(path, {'schema_version': '1.0', 'generated_by': 'session_step_runner.py', 'actions': rows})


def mark_state_attention(project: Path, state: dict[str, Any], *, reason: str, action: dict[str, Any]) -> dict[str, Any]:
    attention = mark_attention(project, reason=reason, suggested_next_step='Review this item, then run agent continue.', action=action)
    state.update({'status': 'needs_attention', 'attention_required': True, 'pause_reason': reason, 'resume_available': True})
    save_session_state(project, state)
    append_session_event(project, 'needs_attention', {'reason': reason, 'action_id': action.get('selected_action_id') or action.get('action_id') or ''})
    sync_cockpit(project)
    generate_digest(project)
    return {'state': state, 'attention': attention, 'summary': None, 'outcome': 'blocked'}


def run_session_step(project: Path, *, state: dict[str, Any], mode: str = 'standard', backend: str = 'mock', budget: dict[str, int] | None = None) -> dict[str, Any]:
    ensure_project_map(project, str(state.get('goal') or ''))
    selected = select_next_action(project, mode=mode)
    action_id = str(selected.get('selected_action_id') or selected.get('action_id') or '')
    state.update({'current_action_id': action_id, 'next_action_id': action_id, 'status': 'active', 'attention_required': False, 'pause_reason': ''})
    save_session_state(project, state)
    append_session_event(project, 'step_selected', {'action_id': action_id, 'source': selected.get('source', '')})
    task_profile = classify_task_profile(selected, session_state=state)
    routing = route_worker(project, task_profile=task_profile, requested_worker=backend or 'auto', execution_mode=str(selected.get('execution_mode') or ''))
    append_session_event(project, 'worker_routed', {'action_id': action_id, 'worker': routing.get('selected_worker', ''), 'mode': routing.get('execution_mode', '')})
    if selected.get('execution_mode') == 'needs_attention' or not routing.get('execution_allowed'):
        reason = str(routing.get('blocked_reason') or selected.get('reason') or 'selected action needs attention')
        return mark_state_attention(project, state, reason=reason, action={**selected, 'routing_decision': routing})

    checkpoint = create_checkpoint(project, action_id=action_id, title=str(selected.get('title') or action_id))
    state.update({'last_checkpoint_id': checkpoint.get('checkpoint_id', '')})
    save_session_state(project, state)
    append_session_event(project, 'checkpoint_created', {'checkpoint_id': checkpoint.get('checkpoint_id', ''), 'action_id': action_id})

    step_number = int(state.get('current_step') or 0) + 1
    result = execute_routed_worker(project, action=selected, routing_decision=routing, step_number=step_number)
    final_result = result['final_result']
    execution = result['execution']
    update = update_project_map(project, run_id=result['run_id'], action=selected, execution_result=execution, final_result=final_result)
    summary = build_progress_summary(project, action=selected, execution=execution, final_result=final_result, mode=mode)
    classification = classify_step_result(final_result, execution, selected)
    changed_files = summary.get('changed_files') or update.get('changed_files') or []
    history_row = {
        'at': utc_now(),
        'step': step_number,
        'session_id': state.get('session_id', ''),
        'action_id': action_id,
        'title': selected.get('title', ''),
        'source': selected.get('source', ''),
        'trust_zone': selected.get('trust_zone', ''),
        'execution_mode': selected.get('execution_mode', ''),
        'worker_role': routing.get('worker_role', ''),
        'selected_worker': routing.get('selected_worker', ''),
        'routing_mode': routing.get('execution_mode', ''),
        'run_id': result['run_id'],
        'checkpoint_id': checkpoint.get('checkpoint_id', ''),
        'outcome': classification.get('outcome', ''),
        'status': classification.get('status', ''),
        'changed_files': changed_files,
    }
    append_session_history(project, history_row)
    append_autopilot_history(
        project,
        {
            'at': history_row['at'],
            'action_id': action_id,
            'title': selected.get('title', ''),
            'target_files': selected.get('target_files') or [],
            'execution_mode': selected.get('execution_mode', ''),
            'worker_role': routing.get('worker_role', ''),
            'routing_mode': routing.get('execution_mode', ''),
            'changed_files': changed_files,
            'run_id': result['run_id'],
            'result': summary.get('result'),
            'status': summary.get('status'),
            'checkpoint_id': checkpoint.get('checkpoint_id'),
        },
    )
    state['current_step'] = step_number
    state['last_action_id'] = action_id
    state['current_action_id'] = ''
    state['completed_steps'] = int(state.get('completed_steps') or 0) + (1 if classification.get('outcome') in {'delivered', 'dry_run_only'} else 0)
    state['failed_steps'] = int(state.get('failed_steps') or 0) + (1 if classification.get('status') == 'needs_attention' and classification.get('outcome') not in {'dry_run_only'} else 0)
    if classification.get('pause'):
        attention = mark_attention(project, reason=str(classification.get('reason') or 'review required'), suggested_next_step='Review the result, then run agent continue when ready.', action=selected)
        state.update({'status': 'needs_attention', 'attention_required': True, 'pause_reason': classification.get('reason', ''), 'resume_available': True})
    else:
        state.update({'status': 'active', 'attention_required': False, 'pause_reason': '', 'resume_available': True})
        next_selected = select_next_action(project, mode=mode)
        state['next_action_id'] = str(next_selected.get('selected_action_id') or '')
        attention = None

    budget_result = budget_decision(state, load_session_history(project), normalize_budget({**(budget or {}), 'max_steps': int(state.get('max_steps') or 5)}))
    if budget_result['status'] == 'paused' and state.get('status') == 'active':
        state.update({'status': 'paused', 'pause_reason': ', '.join(budget_result.get('reasons') or ['budget reached']), 'resume_available': True})
    elif budget_result['status'] == 'needs_attention':
        reason = ', '.join(budget_result.get('reasons') or ['budget needs attention'])
        attention = mark_attention(project, reason=reason, suggested_next_step='Review session budget, then continue or stop.', action=selected)
        state.update({'status': 'needs_attention', 'attention_required': True, 'pause_reason': reason, 'resume_available': True})

    save_session_state(project, state)
    append_session_event(project, 'step_finished', {'action_id': action_id, 'outcome': classification.get('outcome'), 'status': state.get('status')})
    sync_cockpit(project)
    generate_digest(project)
    return {'state': state, 'selected_action': selected, 'summary': summary, 'attention': attention, 'classification': classification, 'result': result}


def main() -> int:
    parser = argparse.ArgumentParser(description='Run one long-running session step.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--state', required=True)
    parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='standard')
    parser.add_argument('--backend', default='mock')
    args = parser.parse_args()
    project = project_root(args.workspace)
    state = load_json(Path(args.state).resolve())
    payload = run_session_step(project, state=state, mode=args.mode, backend=args.backend)
    print(json.dumps({'status': 'ok', 'session_status': payload['state'].get('status')}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
