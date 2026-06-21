#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from first_run_guidance_engine import render_guidance
from job_state_store import load_current_job, sync_job_from_session, write_job_digest
from runtime_common import load_json
from runtime_common import project_root


def _selected_action(project: Path) -> dict:
    return load_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json')


def _action_status(status: str, action: dict, attention: str) -> str:
    if action.get('execution_mode') == 'needs_attention' or str(action.get('trust_zone')) == 'blocked':
        return 'Blocked with reason'
    if action.get('preview_only') or action.get('execution_mode') == 'preview':
        return 'Preview recommended'
    if action.get('source') in {'seed_prompt', 'user_goal'} or action.get('action_source') in {'seed_prompt', 'user_goal'}:
        return 'Ready for starter action'
    return status


def _evidence_lines(action: dict) -> list[str]:
    rows = []
    for item in action.get('evidence') or []:
        if not isinstance(item, dict):
            continue
        kind = item.get('evidence_type') or item.get('kind') or 'evidence'
        path = item.get('path') or ''
        if kind == 'seed_prompt':
            rows.append(f'- Found seed prompt: {path}')
        elif kind == 'user_goal_intent':
            rows.append('- Using the user goal as starter intent evidence')
        elif path:
            rows.append(f'- {kind}: {path}')
    return rows or ['- not available']


def _target_lines(action: dict) -> list[str]:
    targets = [str(item) for item in action.get('target_files') or [] if str(item or '').strip()]
    if not targets:
        return [f'- {action.get("title") or "not available"}']
    return [f'- {action.get("title") or "Create starter project documents"}', *[f'  - {target}' for target in targets]]


def _autopilot_line(action: dict) -> str:
    if action.get('execution_mode') == 'needs_attention':
        return 'Not eligible until the reason is reviewed.'
    if action.get('preview_only') or action.get('execution_mode') == 'preview':
        return 'Preview only. Existing files will not be overwritten.'
    if action.get('autopilot_eligible'):
        return 'Eligible. Only trusted docs are targeted; no scripts will run.'
    return 'Not eligible.'


def render_job_inbox(project: Path, *, refresh: bool = True) -> str:
    if refresh and not load_current_job(project) and not load_json(project / '.zoo-agent' / 'session' / 'session_state.json'):
        return render_guidance(project)
    job = sync_job_from_session(project) if refresh else load_current_job(project)
    if not job or not job.get('goal'):
        return render_guidance(project)
    write_job_digest(project, job)
    status = job.get('status') or 'not_started'
    action = _selected_action(project)
    display_status = _action_status(str(status), action, str(job.get('attention_reason') or ''))
    next_action = action.get('title') or job.get('next_action') or 'not available'
    attention = job.get('attention_reason') or ('review required' if job.get('attention_required') else 'none')
    reason = action.get('reason') or action.get('blocked_reason') or attention
    risk_level = action.get('risk_level') or 'unknown'
    lines = [
        'AI Project Operator',
        '',
        'Current job:',
        str(job.get('goal') or 'not available'),
        '',
        'Status:',
        str(display_status),
        '',
        'Reason:',
        f'- {reason}',
        '',
        'Evidence:',
        *_evidence_lines(action),
        '',
        'What happened:',
        f'- Last action: {job.get("last_action") or "not recorded yet"}',
        f'- Job digest: {job.get("digest_path") or ".zoo-agent/jobs/job_digest.md"}',
        '',
        'Suggested next action:',
        *_target_lines({**action, 'title': next_action}),
        '',
        'Risk level:',
        f'- {risk_level}',
        '',
        'Autopilot:',
        f'- {_autopilot_line(action)}',
        '',
        'Needs attention:',
        f'- {attention}',
        '',
        'Available outputs:',
        f'- Cockpit: {job.get("cockpit_path") or ".zoo-agent/cockpit/index.html"}',
        f'- Release pack: {"available" if job.get("release_pack_available") else "not generated yet"}',
        f'- PR draft: {"available" if job.get("pr_draft_available") else "not generated yet"}',
        '',
        'Suggested commands:',
        'agent continue',
        'agent cockpit',
        'agent undo',
        'agent release',
        'agent pr',
        '',
        'How to continue:',
        'agent continue',
        '',
        'Tip: most of the time, use `agent "<goal>"` and `agent`.',
    ]
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Render the product-level project job inbox.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--no-refresh', action='store_true')
    args = parser.parse_args()
    print(render_job_inbox(project_root(args.workspace), refresh=not args.no_refresh))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
