#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from background_job_policy import decide_policy, write_policy_report
from job_inbox_renderer import render_job_inbox
from job_state_store import (
    JOB_ACTIVE_STATUSES,
    append_job_event,
    load_current_job,
    save_current_job,
    sync_job_from_session,
    write_job_digest,
)
from runtime_common import load_json, project_root
from session_runtime_engine import continue_session, start_session, stop_session, undo_session


def _same_goal(left: str, right: str) -> bool:
    left_norm = ' '.join(left.lower().split())
    right_norm = ' '.join(right.lower().split())
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    left_tokens = {part for part in left_norm.split() if len(part) > 2}
    right_tokens = {part for part in right_norm.split() if len(part) > 2}
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1) >= 0.6


def _action_display_status(job: dict[str, Any], action: dict[str, Any]) -> str:
    if action.get('execution_mode') == 'needs_attention' or action.get('trust_zone') == 'blocked':
        return 'Blocked with reason'
    if action.get('preview_only') or action.get('execution_mode') == 'preview':
        return 'Preview recommended'
    if action.get('source') in {'seed_prompt', 'user_goal'} or action.get('action_source') in {'seed_prompt', 'user_goal'}:
        return 'Ready for starter action'
    return str(job.get('status') or 'updated')


def _action_evidence_lines(action: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in action.get('evidence') or []:
        if not isinstance(item, dict):
            continue
        kind = item.get('evidence_type') or item.get('kind') or 'evidence'
        path = item.get('path') or 'available'
        if kind == 'seed_prompt':
            lines.append(f'- Found seed prompt: {path}')
        elif kind == 'user_goal_intent':
            lines.append('- Using the user goal as starter intent evidence')
        else:
            lines.append(f'- {kind}: {path}')
    return lines or ['- not available']


def _autopilot_line(action: dict[str, Any]) -> str:
    if action.get('execution_mode') == 'needs_attention':
        return '- Not eligible until the reason is reviewed.'
    if action.get('preview_only') or action.get('execution_mode') == 'preview':
        return '- Preview only. Existing files will not be overwritten.'
    if action.get('autopilot_eligible'):
        return '- Eligible. Only trusted docs are targeted; no scripts will run.'
    return '- Not eligible.'


def _summary(project: Path, job: dict[str, Any], *, started: bool = False, hint: str = '') -> str:
    action = load_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json')
    display_status = _action_display_status(job, action)
    if display_status == 'Ready for starter action':
        prefix = 'Ready for starter action.\nProject job saved.'
    elif display_status == 'Preview recommended':
        prefix = 'Preview ready.\nProject job saved.'
    elif job.get('status') == 'needs_attention':
        prefix = 'Needs attention.\nProject job saved.'
    else:
        prefix = 'Done.\nStarted project job.' if started else 'Done.\nProject job updated.'
    lines = [
        prefix,
        '',
        'Goal:',
        str(job.get('goal') or 'not available'),
        '',
        'Status:',
        display_status,
        '',
        'Reason:',
        f'- {action.get("reason") or action.get("blocked_reason") or job.get("attention_reason") or "Project job updated."}',
        '',
        'Evidence:',
        *_action_evidence_lines(action),
        '',
        'Suggested next action:',
        f'- {action.get("title") or job.get("next_action") or "not available"}',
        *[f'  - {target}' for target in (action.get('target_files') or [])],
        '',
        'Risk level:',
        f'- {action.get("risk_level") or "unknown"}',
        '',
        'Autopilot:',
        _autopilot_line(action),
        '',
        'Working mode:',
        'Project Map-backed Autopilot',
        '',
        'What happened:',
        '- Project map initialized or refreshed',
        '- Next action selected',
        '- Session state saved',
        '- Cockpit available',
    ]
    if hint:
        lines.extend(['', 'Tip:', hint])
    if job.get('status') == 'needs_attention':
        lines.extend(['', 'Reason:', f'- {job.get("attention_reason") or "review required"}'])
    lines.extend(
        [
            '',
            'Check later:',
            'agent',
            '',
            'Useful:',
            'agent cockpit',
            'agent continue',
            'agent undo',
            '',
            'Undo:',
            'agent undo',
        ]
    )
    write_job_digest(project, job)
    return '\n'.join(lines)


def start_or_update_job(project: Path, goal: str, *, mode: str = 'standard', max_steps: int = 0, backend: str = '', steps: int = 0) -> dict[str, Any]:
    existing = load_current_job(project)
    decision = decide_policy(goal, existing_job=bool(existing))
    write_policy_report(project, decision)
    if existing and existing.get('status') in JOB_ACTIVE_STATUSES and not _same_goal(str(existing.get('goal') or ''), goal):
        message = (
            'Existing job found.\n\n'
            f'Current job:\n{existing.get("goal")}\n\n'
            'Use:\nagent\nagent continue\nagent stop\n\n'
            'The existing job was not overwritten.'
        )
        return {'status': 'blocked', 'job': existing, 'message': message}
    if existing and existing.get('status') in JOB_ACTIVE_STATUSES:
        result = continue_session(project, mode=mode, steps=max(1, steps or 1), backend=backend)
        job = sync_job_from_session(project, goal=goal or str(existing.get('goal') or ''))
        append_job_event(project, 'job_continued_from_goal', {'job_id': job.get('job_id', ''), 'goal': job.get('goal', '')})
        return {'status': result.get('status'), 'job': job, 'message': _summary(project, job, started=False, hint=str(decision.get('hint') or ''))}
    result = start_session(project, goal=goal, mode=mode, max_steps=max_steps, backend=backend, steps=steps)
    job = sync_job_from_session(project, goal=goal)
    append_job_event(project, 'job_started', {'job_id': job.get('job_id', ''), 'goal': goal})
    return {'status': result.get('status'), 'job': job, 'message': _summary(project, job, started=True, hint=str(decision.get('hint') or ''))}


def show_job_inbox(project: Path) -> dict[str, Any]:
    text = render_job_inbox(project)
    return {'status': 'ok', 'message': text, 'job': load_current_job(project)}


def continue_job(project: Path, *, mode: str = 'standard', steps: int = 1, backend: str = '') -> dict[str, Any]:
    result = continue_session(project, mode=mode, steps=steps, backend=backend)
    job = sync_job_from_session(project)
    append_job_event(project, 'job_continued', {'job_id': job.get('job_id', ''), 'status': job.get('status', '')})
    return {'status': result.get('status'), 'job': job, 'message': render_job_inbox(project, refresh=False)}


def stop_job(project: Path) -> dict[str, Any]:
    result = stop_session(project)
    job = sync_job_from_session(project)
    job['status'] = 'stopped'
    save_current_job(project, job)
    append_job_event(project, 'job_stopped', {'job_id': job.get('job_id', '')})
    return {'status': result.get('status'), 'job': job, 'message': render_job_inbox(project, refresh=False)}


def undo_job(project: Path) -> dict[str, Any]:
    result = undo_session(project)
    job = sync_job_from_session(project)
    append_job_event(project, 'job_undo_checked', {'job_id': job.get('job_id', ''), 'checkpoint': (result.get('checkpoint') or {}).get('checkpoint_id', '')})
    return {'status': result.get('status'), 'job': job, 'message': render_job_inbox(project, refresh=False)}


def main() -> int:
    parser = argparse.ArgumentParser(description='Product-level project job controller.')
    parser.add_argument('goal', nargs='*')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='standard')
    parser.add_argument('--max-steps', type=int, default=0)
    parser.add_argument('--steps', type=int, default=0)
    parser.add_argument('--backend', default='')
    parser.add_argument('--start', action='store_true')
    parser.add_argument('--continue-job', action='store_true')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--undo', action='store_true')
    parser.add_argument('--inbox', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    if args.inbox:
        payload = show_job_inbox(project)
    elif args.continue_job:
        payload = continue_job(project, mode=args.mode, steps=args.steps or 1, backend=args.backend)
    elif args.stop:
        payload = stop_job(project)
    elif args.undo:
        payload = undo_job(project)
    else:
        goal = ' '.join(args.goal).strip()
        if not goal:
            payload = show_job_inbox(project)
        else:
            payload = start_or_update_job(project, goal, mode=args.mode, max_steps=args.max_steps, backend=args.backend, steps=args.steps)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload.get('message') or render_job_inbox(project))
    return 0 if payload.get('status') != 'blocked' else 2


if __name__ == '__main__':
    raise SystemExit(main())
