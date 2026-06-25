#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from backend_registry import read_backend_selection
from runtime_common import project_root, set_active_goal, utc_now
from session_budget_manager import DEFAULT_BUDGET
from session_cockpit_sync import sync_cockpit
from session_digest_generator import generate_digest, latest_checkpoint, selected_action
from session_resume_engine import recover_session
from session_state_store import (
    acquire_session_lock,
    append_session_event,
    default_session_state,
    load_session_state,
    release_session_lock,
    save_session_state,
)
from session_step_runner import ensure_project_map, run_session_step

ACTIVE_STATUSES = {'active', 'paused', 'needs_attention'}


def user_summary(project: Path, state: dict[str, Any], *, title: str = '') -> str:
    status = str(state.get('status') or 'unknown')
    digest = '.zoo-agent/session/session_digest.md'
    cockpit = '.zoo-agent/cockpit/index.html'
    next_action = (selected_action(project) or {}).get('title') or state.get('next_action_id') or 'not available'
    if status == 'needs_attention':
        return (
            'Needs attention.\n'
            'Reason:\n'
            f'* {state.get("pause_reason") or "review required"}\n\n'
            'Suggested next step:\n'
            '* Review the session digest, then run agent continue or agent stop.\n\n'
            f'Digest:\n{digest}\n\nCockpit:\n{cockpit}'
        )
    heading = 'Done.' if status in {'active', 'paused', 'completed'} else 'Session updated.'
    return (
        f'{heading}\n'
        f'Session:\n* status: {status}\n* goal: {state.get("goal") or "not available"}\n* next: {next_action}\n\n'
        f'Digest:\n{digest}\n\nCockpit:\n{cockpit}\n\n'
        'Undo:\nagent undo\n\n'
        'Commands:\nagent status\nagent continue\nagent stop\nagent undo'
    )


def status_payload(project: Path) -> dict[str, Any]:
    state, meta = load_session_state(project)
    if not state:
        return {
            'task': 'session',
            'mode': 'status',
            'result': 'Session: status: not_started; goal: not available; next: not available; digest: .zoo-agent/session/session_digest.md; cockpit: .zoo-agent/cockpit/index.html',
            'meta': meta,
        }
    next_action = (selected_action(project) or {}).get('title') or state.get('next_action_id') or 'not available'
    result = (
        f'Session: status: {state.get("status")}; '
        f'goal: {state.get("goal") or "not available"}; '
        f'next: {next_action}; '
        f'digest: .zoo-agent/session/session_digest.md; '
        f'cockpit: .zoo-agent/cockpit/index.html'
    )
    return {'task': state.get('goal') or 'session', 'mode': 'status', 'result': result}


def start_session(
    project: Path, *, goal: str, mode: str = 'standard', max_steps: int = 0, backend: str = '', steps: int = 0
) -> dict[str, Any]:
    existing, _ = load_session_state(project)
    if existing and existing.get('status') in ACTIVE_STATUSES:
        return {
            'status': 'blocked',
            'state': existing,
            'message': 'A session is already available. Run agent continue or agent stop.',
        }
    total_budget = max_steps or DEFAULT_BUDGET['max_steps']
    state = default_session_state(project, goal=goal, max_steps=total_budget)
    state.update(
        {
            'status': 'active',
            'created_at': utc_now(),
            'updated_at': utc_now(),
            'mode': mode,
            'backend': backend or read_backend_selection(project, default='auto'),
        }
    )
    set_active_goal(project, goal, source='session_runtime_engine.py')
    ensure_project_map(project, goal)
    save_session_state(project, state)
    append_session_event(project, 'session_started', {'goal': goal, 'session_id': state['session_id']})
    run_count = steps or (max_steps if mode == 'autopilot' and max_steps else 1)
    result: dict[str, Any] = {'state': state}
    lock = acquire_session_lock(project, session_id=state['session_id'])
    if not lock.get('acquired'):
        state.update(
            {
                'status': 'needs_attention',
                'attention_required': True,
                'pause_reason': lock.get('reason', 'session lock unavailable'),
            }
        )
        save_session_state(project, state)
        generate_digest(project)
        sync_cockpit(project)
        return {'status': 'needs_attention', 'state': state, 'message': state['pause_reason']}
    try:
        for _ in range(max(1, run_count)):
            current, _ = load_session_state(project)
            if current.get('status') in {'stopped', 'completed', 'failed'}:
                break
            result = run_session_step(
                project,
                state=current,
                mode=mode,
                backend=str(state.get('backend') or 'auto'),
                budget={'max_steps': total_budget},
            )
            state = result['state']
            if state.get('status') != 'active':
                break
    finally:
        release_session_lock(project)
    generate_digest(project)
    sync_cockpit(project)
    return {'status': state.get('status'), 'state': state, 'step_result': result}


def continue_session(project: Path, *, mode: str = 'standard', steps: int = 1, backend: str = '') -> dict[str, Any]:
    recover = recover_session(project)
    state, meta = load_session_state(project)
    if not state:
        return {
            'status': 'blocked',
            'state': {},
            'message': recover.get('reason') or meta.get('status') or 'no session found',
        }
    if state.get('status') in {'stopped', 'completed', 'failed'}:
        generate_digest(project)
        sync_cockpit(project)
        return {
            'status': 'blocked',
            'state': state,
            'message': f'session is {state.get("status")}; start a new session to continue',
        }
    if not recover.get('safe_to_continue', True):
        return {'status': 'needs_attention', 'state': state, 'message': recover.get('reason') or 'recovery needed'}
    lock = acquire_session_lock(project, session_id=str(state.get('session_id') or ''))
    if not lock.get('acquired'):
        state.update(
            {
                'status': 'needs_attention',
                'attention_required': True,
                'pause_reason': lock.get('reason', 'session lock unavailable'),
            }
        )
        save_session_state(project, state)
        generate_digest(project)
        sync_cockpit(project)
        return {'status': 'needs_attention', 'state': state, 'message': state['pause_reason']}
    result: dict[str, Any] = {'state': state}
    try:
        for _ in range(max(1, steps)):
            current, _ = load_session_state(project)
            if current.get('status') in {'stopped', 'completed', 'failed'}:
                break
            current.update({'status': 'active', 'attention_required': False, 'pause_reason': ''})
            result = run_session_step(
                project,
                state=current,
                mode=mode or str(current.get('mode') or 'standard'),
                backend=backend or str(current.get('backend') or read_backend_selection(project, default='auto')),
                budget={'max_steps': int(current.get('max_steps') or DEFAULT_BUDGET['max_steps'])},
            )
            if result['state'].get('status') != 'active':
                break
    finally:
        release_session_lock(project)
    generate_digest(project)
    sync_cockpit(project)
    return {'status': result['state'].get('status'), 'state': result['state'], 'step_result': result}


def stop_session(project: Path) -> dict[str, Any]:
    state, _ = load_session_state(project)
    if not state:
        state = default_session_state(project)
    state.update(
        {
            'status': 'stopped',
            'resume_available': False,
            'attention_required': False,
            'pause_reason': '',
            'updated_at': utc_now(),
        }
    )
    save_session_state(project, state)
    append_session_event(project, 'session_stopped', {'session_id': state.get('session_id', '')})
    generate_digest(project)
    sync_cockpit(project)
    return {'status': 'stopped', 'state': state}


def undo_session(project: Path) -> dict[str, Any]:
    state, _ = load_session_state(project)
    checkpoint = latest_checkpoint(project)
    if not state:
        state = default_session_state(project)
    if checkpoint:
        state.update(
            {
                'status': 'paused',
                'pause_reason': f'undo available at {checkpoint.get("checkpoint_id")}',
                'resume_available': True,
                'attention_required': False,
            }
        )
        save_session_state(project, state)
        append_session_event(
            project, 'undo_checkpoint_selected', {'checkpoint_id': checkpoint.get('checkpoint_id', '')}
        )
    generate_digest(project)
    sync_cockpit(project)
    return {'status': 'ok' if checkpoint else 'empty', 'state': state, 'checkpoint': checkpoint}


def recover(project: Path) -> dict[str, Any]:
    report = recover_session(project)
    generate_digest(project)
    sync_cockpit(project)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Long-running AI Project Operator session runtime.')
    parser.add_argument('goal', nargs='*')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='standard')
    parser.add_argument('--max-steps', type=int, default=0)
    parser.add_argument('--steps', type=int, default=1)
    parser.add_argument('--backend', default='')
    parser.add_argument('--start', action='store_true')
    parser.add_argument('--continue-session', action='store_true')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--undo', action='store_true')
    parser.add_argument('--recover', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    if args.status:
        payload = status_payload(project)
    elif args.stop:
        payload = stop_session(project)
    elif args.undo:
        payload = undo_session(project)
    elif args.recover:
        payload = recover(project)
    elif args.continue_session:
        payload = continue_session(project, mode=args.mode, steps=args.steps, backend=args.backend)
    else:
        goal = ' '.join(args.goal).strip()
        if not goal:
            raise SystemExit('Missing project goal.')
        payload = start_session(project, goal=goal, mode=args.mode, max_steps=args.max_steps, backend=args.backend)
    if args.json or args.status or args.recover:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        state = payload.get('state') or {}
        print(user_summary(project, state))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
