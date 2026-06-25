#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from project_map_builder import build_project_map, render_markdown
from project_map_schema import map_dir
from runtime_common import project_root, write_json
from session_cockpit_sync import sync_cockpit
from session_digest_generator import latest_checkpoint
from session_state_store import load_session_state, lock_status, save_session_state


def recovery_report(project: Path) -> dict[str, Any]:
    state, meta = load_session_state(project)
    lock = lock_status(project)
    report = {
        'schema_version': '1.0',
        'generated_by': 'session_resume_engine.py',
        'recovery_needed': False,
        'recovery_status': 'clean',
        'last_known_step': int(state.get('current_step') or 0) if state else 0,
        'last_checkpoint': latest_checkpoint(project).get('checkpoint_id', ''),
        'safe_to_continue': True,
        'reason': '',
    }
    if meta.get('corrupted'):
        report.update(
            {
                'recovery_needed': True,
                'recovery_status': 'needs_attention',
                'safe_to_continue': False,
                'reason': 'session_state_corrupted',
            }
        )
    elif not state:
        report.update(
            {
                'recovery_needed': True,
                'recovery_status': 'needs_attention',
                'safe_to_continue': False,
                'reason': 'no_session_state',
            }
        )
    elif state.get('status') in {'failed'}:
        report.update(
            {
                'recovery_needed': True,
                'recovery_status': 'needs_attention',
                'safe_to_continue': False,
                'reason': 'last_session_failed',
            }
        )
    if lock.get('locked') and lock.get('stale'):
        report.update(
            {
                'recovery_needed': True,
                'recovery_status': 'recovered',
                'safe_to_continue': True,
                'reason': 'stale_lock_recovered',
            }
        )
    elif lock.get('locked') and not lock.get('stale'):
        report.update(
            {
                'recovery_needed': True,
                'recovery_status': 'needs_attention',
                'safe_to_continue': False,
                'reason': 'session_locked',
            }
        )
    return report


def recover_session(project: Path) -> dict[str, Any]:
    report = recovery_report(project)
    if report.get('safe_to_continue') and not (map_dir(project) / 'project_map.json').exists():
        state, _ = load_session_state(project)
        project_map, project_state, evidence = build_project_map(project, main_goal=str(state.get('goal') or ''))
        write_json(map_dir(project) / 'project_map.json', project_map)
        write_json(map_dir(project) / 'project_state.json', project_state)
        write_json(map_dir(project) / 'map_evidence.json', evidence)
        md = map_dir(project) / 'project_map.md'
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(render_markdown(project_map), encoding='utf-8')
        report.update({'recovery_needed': True, 'recovery_status': 'recovered', 'reason': 'project_map_rebuilt'})
    sync = sync_cockpit(project)
    if sync.get('status') == 'failed' and report.get('safe_to_continue'):
        report.update(
            {
                'recovery_needed': True,
                'recovery_status': 'needs_attention',
                'safe_to_continue': False,
                'reason': 'cockpit_sync_failed',
            }
        )
    state, _ = load_session_state(project)
    if state and report.get('recovery_needed'):
        state['resume_available'] = bool(report.get('safe_to_continue'))
        if not report.get('safe_to_continue') and state.get('status') not in {'stopped', 'completed'}:
            state['status'] = 'needs_attention'
            state['attention_required'] = True
            state['pause_reason'] = report.get('reason', '')
        save_session_state(project, state)
    write_json(project / '.zoo-agent' / 'session' / 'recovery_report.json', report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Recover or inspect a long-running session.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = recovery_report(project) if args.check_only else recover_session(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
