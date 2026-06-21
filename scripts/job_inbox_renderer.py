#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from first_run_guidance_engine import render_guidance
from job_state_store import load_current_job, sync_job_from_session, write_job_digest
from runtime_common import load_json
from runtime_common import project_root


def render_job_inbox(project: Path, *, refresh: bool = True) -> str:
    if refresh and not load_current_job(project) and not load_json(project / '.zoo-agent' / 'session' / 'session_state.json'):
        return render_guidance(project)
    job = sync_job_from_session(project) if refresh else load_current_job(project)
    if not job or not job.get('goal'):
        return render_guidance(project)
    write_job_digest(project, job)
    status = job.get('status') or 'not_started'
    next_action = job.get('next_action') or 'not available'
    attention = job.get('attention_reason') or ('review required' if job.get('attention_required') else 'none')
    lines = [
        'AI Project Operator',
        '',
        'Current job:',
        str(job.get('goal') or 'not available'),
        '',
        'Status:',
        str(status),
        '',
        'What happened:',
        f'- Last action: {job.get("last_action") or "not recorded yet"}',
        f'- Job digest: {job.get("digest_path") or ".zoo-agent/jobs/job_digest.md"}',
        '',
        'Next action:',
        f'- {next_action}',
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
