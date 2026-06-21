#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


JOB_SCHEMA_VERSION = '1.0'
JOB_ACTIVE_STATUSES = {'active', 'paused', 'needs_attention'}


def jobs_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'jobs'


def current_job_path(project: Path) -> Path:
    return jobs_dir(project) / 'current_job.json'


def job_history_path(project: Path) -> Path:
    return jobs_dir(project) / 'job_history.json'


def job_events_path(project: Path) -> Path:
    return jobs_dir(project) / 'job_events.jsonl'


def job_digest_path(project: Path) -> Path:
    return jobs_dir(project) / 'job_digest.md'


def default_job(project: Path, *, goal: str = '', linked_session_id: str = '') -> dict[str, Any]:
    now = utc_now()
    return {
        'schema_version': JOB_SCHEMA_VERSION,
        'generated_by': 'job_state_store.py',
        'job_id': f'job-{int(time.time())}',
        'goal': goal,
        'status': 'not_started',
        'linked_session_id': linked_session_id,
        'created_at': now,
        'updated_at': now,
        'last_checked_at': now,
        'last_action': '',
        'next_action': '',
        'attention_required': False,
        'attention_reason': '',
        'cockpit_path': '.zoo-agent/cockpit/index.html',
        'digest_path': '.zoo-agent/jobs/job_digest.md',
        'release_pack_available': False,
        'pr_draft_available': False,
    }


def load_current_job(project: Path) -> dict[str, Any]:
    return load_json(current_job_path(project))


def save_current_job(project: Path, job: dict[str, Any]) -> dict[str, Any]:
    payload = {**job, 'schema_version': JOB_SCHEMA_VERSION, 'generated_by': 'job_state_store.py', 'updated_at': utc_now()}
    write_json(current_job_path(project), payload)
    append_job_history(project, payload)
    return payload


def load_job_history(project: Path) -> dict[str, Any]:
    payload = load_json(job_history_path(project))
    if payload:
        return payload
    return {'schema_version': JOB_SCHEMA_VERSION, 'generated_by': 'job_state_store.py', 'jobs': []}


def append_job_history(project: Path, job: dict[str, Any]) -> dict[str, Any]:
    history = load_job_history(project)
    jobs = [item for item in history.get('jobs') or [] if isinstance(item, dict)]
    compact = {
        'job_id': job.get('job_id', ''),
        'goal': job.get('goal', ''),
        'status': job.get('status', ''),
        'linked_session_id': job.get('linked_session_id', ''),
        'updated_at': job.get('updated_at') or utc_now(),
        'next_action': job.get('next_action', ''),
        'attention_required': bool(job.get('attention_required')),
    }
    jobs = [item for item in jobs if item.get('job_id') != compact['job_id']]
    jobs.append(compact)
    history.update({'schema_version': JOB_SCHEMA_VERSION, 'generated_by': 'job_state_store.py', 'updated_at': utc_now(), 'jobs': jobs[-50:]})
    write_json(job_history_path(project), history)
    return history


def append_job_event(project: Path, event_type: str, payload: dict[str, Any] | None = None) -> None:
    path = job_events_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {'at': utc_now(), 'type': event_type, **(payload or {})}
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + '\n')


def _read_session_state(project: Path) -> dict[str, Any]:
    return load_json(project / '.zoo-agent' / 'session' / 'session_state.json')


def _read_selected_action(project: Path) -> dict[str, Any]:
    return load_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json')


def sync_job_from_session(project: Path, *, goal: str = '') -> dict[str, Any]:
    session = _read_session_state(project)
    selected = _read_selected_action(project)
    existing = load_current_job(project)
    linked_session_id = str(session.get('session_id') or existing.get('linked_session_id') or '')
    job = existing or default_job(project, goal=goal or str(session.get('goal') or ''), linked_session_id=linked_session_id)
    if not job.get('job_id'):
        job['job_id'] = default_job(project).get('job_id')
    job.update(
        {
            'goal': goal or str(session.get('goal') or job.get('goal') or ''),
            'status': str(session.get('status') or job.get('status') or 'not_started'),
            'linked_session_id': linked_session_id,
            'last_checked_at': utc_now(),
            'last_action': str(session.get('last_action_id') or job.get('last_action') or ''),
            'next_action': str(selected.get('title') or session.get('next_action_id') or job.get('next_action') or ''),
            'attention_required': bool(session.get('attention_required')),
            'attention_reason': str(session.get('pause_reason') or ''),
            'cockpit_path': '.zoo-agent/cockpit/index.html',
            'digest_path': '.zoo-agent/jobs/job_digest.md',
            'release_pack_available': (project / '.zoo-agent' / 'release' / 'release_workflow_report.md').exists(),
            'pr_draft_available': (project / '.zoo-agent' / 'release' / 'pr_draft.md').exists(),
        }
    )
    return save_current_job(project, job)


def write_job_digest(project: Path, job: dict[str, Any]) -> dict[str, Any]:
    lines = [
        '# Project Job Digest',
        '',
        f'Generated: {utc_now()}',
        '',
        '## Goal',
        '',
        job.get('goal') or 'No project job yet.',
        '',
        '## Status',
        '',
        f'- Status: {job.get("status") or "not_started"}',
        f'- Next action: {job.get("next_action") or "not available"}',
        f'- Attention required: {bool(job.get("attention_required"))}',
        '',
        '## Attention',
        '',
        f'- {job.get("attention_reason") or "No attention needed right now."}',
        '',
        '## Outputs',
        '',
        f'- Cockpit: {job.get("cockpit_path") or ".zoo-agent/cockpit/index.html"}',
        f'- Release pack available: {bool(job.get("release_pack_available"))}',
        f'- PR draft available: {bool(job.get("pr_draft_available"))}',
        '',
        '## Suggested Commands',
        '',
        '- agent',
        '- agent continue',
        '- agent cockpit',
        '- agent undo',
        '- agent release',
        '- agent pr',
        '',
    ]
    path = job_digest_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(str(item) for item in lines), encoding='utf-8')
    return {'status': 'ok', 'digest': '.zoo-agent/jobs/job_digest.md'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Inspect product-level project job state.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    job = sync_job_from_session(project)
    write_job_digest(project, job)
    print(json.dumps({'job': job}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
