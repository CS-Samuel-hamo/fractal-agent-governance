#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from first_run_guidance_engine import render_guidance
from job_state_store import load_current_job, sync_job_from_session, write_job_digest
from project_progress_overview import render_interaction_summary
from runtime_common import load_json, project_root
from seed_action_queue import progress_summary as seed_progress_summary


def _selected_action(project: Path) -> dict:
    return load_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json')


def _action_status(status: str, action: dict, attention: str) -> str:
    if status == 'completed':
        return 'Completed'
    if action.get('execution_mode') == 'needs_attention' or str(action.get('trust_zone')) == 'blocked':
        return 'Blocked with reason'
    if action.get('preview_only') or action.get('execution_mode') == 'preview':
        return 'Preview recommended'
    if action.get('source') in {'seed_prompt', 'user_goal'} or action.get('action_source') in {
        'seed_prompt',
        'user_goal',
    }:
        return 'Ready for starter action'
    return status


def _evidence_lines(action: dict, *, seed_source_file: str = '') -> list[str]:
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
    if not rows and seed_source_file:
        rows.append(f'- Found seed prompt: {seed_source_file}')
    return rows or ['- not available']


def _target_lines(action: dict) -> list[str]:
    targets = [str(item) for item in action.get('target_files') or [] if str(item or '').strip()]
    if not targets:
        return [f'- {action.get("title") or "not available"}']
    return [f'- {action.get("title") or "Create starter project documents"}', *[f'  - {target}' for target in targets]]


def _autopilot_line(action: dict) -> str:
    if action.get('source') == 'seed_prompt_queue' and not action.get('selected_action_id'):
        return 'No active automatic action. Current workflow package is ready for review.'
    if action.get('execution_mode') == 'needs_attention':
        return 'Not eligible until the reason is reviewed.'
    if action.get('preview_only') or action.get('execution_mode') == 'preview':
        return 'Preview only. Existing files will not be overwritten.'
    if action.get('autopilot_eligible'):
        return 'Eligible. Only trusted docs are targeted; no scripts will run.'
    return 'Not eligible.'


def _progress_lines(project: Path) -> list[str]:
    progress = seed_progress_summary(project)
    if not progress.get('total_actions'):
        return []
    lines = [
        'Overall progress:',
        f'- Current position: {progress.get("current_position")}',
        f'- Workflow scaffold: {progress.get("completed_actions")}/{progress.get("total_actions")} steps complete',
    ]
    for phase in progress.get('overall_plan') or []:
        if not isinstance(phase, dict):
            continue
        lines.append(f'- {phase.get("phase")}: {phase.get("title")} [{phase.get("status")}]')
    next_action = progress.get('next_action') if isinstance(progress.get('next_action'), dict) else {}
    if next_action.get('title'):
        lines.extend(['', 'Next planned action:', f'- {next_action.get("title")}'])
    else:
        lines.extend(['', 'Next planned stage:', f'- {progress.get("suggested_next_stage")}'])
    return lines


def render_job_inbox(project: Path, *, refresh: bool = True) -> str:
    if (
        refresh
        and not load_current_job(project)
        and not load_json(project / '.zoo-agent' / 'session' / 'session_state.json')
    ):
        return render_guidance(project)
    progress = seed_progress_summary(project)
    has_seed_progress = bool(progress.get('total_actions'))
    job = (
        load_current_job(project)
        if has_seed_progress
        else (sync_job_from_session(project) if refresh else load_current_job(project))
    )
    if not job or not job.get('goal'):
        return render_guidance(project)
    write_job_digest(project, job)
    status = job.get('status') or 'not_started'
    action = _selected_action(project)
    display_status = _action_status(str(status), action, str(job.get('attention_reason') or ''))
    action_title = action.get('title') or job.get('next_action') or 'not available'
    if display_status == 'Completed':
        attention = 'none'
    else:
        attention = job.get('attention_reason') or ('review required' if job.get('attention_required') else 'none')
    reason = action.get('reason') or action.get('blocked_reason') or attention
    pending = int(progress.get('pending_actions') or 0) > 0
    recommended = 'agent continue' if pending else 'agent "<next project goal>"'
    why = reason if reason and reason != 'none' else f'Last action: {job.get("last_action") or "not recorded yet"}'
    lines = render_interaction_summary(
        project,
        status=str(display_status),
        goal=str(job.get('goal') or 'not available'),
        changed_files=[str(item) for item in job.get('last_changed_files') or [] if str(item).strip()],
        why=why,
        next_action=recommended,
        attention='' if attention == 'none' else str(attention),
        stop_reason='needs_attention'
        if attention != 'none' and display_status != 'Completed'
        else 'reviewable_batch_complete',
    )
    lines.extend(
        [
            '',
            'Job details:',
            f'- Last action: {job.get("last_action") or "not recorded yet"}',
            f'- Job digest: {job.get("digest_path") or ".zoo-agent/jobs/job_digest.md"}',
            f'- Suggested action: {action_title}',
            f'- Cockpit: {job.get("cockpit_path") or ".zoo-agent/cockpit/index.html"}',
        ]
    )
    if not pending:
        lines.append('- Continue: not needed right now because the current batch is complete.')
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
