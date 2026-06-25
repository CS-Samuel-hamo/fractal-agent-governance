#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now
from session_state_store import load_session_history, load_session_state, session_digest_path


def latest_checkpoint(project: Path) -> dict[str, Any]:
    payload = load_json(project / '.zoo-agent' / 'autopilot' / 'checkpoints.json')
    checkpoints = [item for item in payload.get('checkpoints') or [] if isinstance(item, dict)]
    return checkpoints[-1] if checkpoints else {}


def latest_attention(project: Path) -> dict[str, Any]:
    return load_json(project / '.zoo-agent' / 'autopilot' / 'attention_required.json')


def selected_action(project: Path) -> dict[str, Any]:
    return load_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json')


def generate_digest(project: Path) -> dict[str, Any]:
    state, meta = load_session_state(project)
    history = load_session_history(project)
    steps = [item for item in history.get('steps') or [] if isinstance(item, dict)]
    checkpoint = latest_checkpoint(project)
    attention = latest_attention(project)
    next_action = selected_action(project)
    changed_files = []
    for item in steps:
        for path in item.get('changed_files') or []:
            if path not in changed_files:
                changed_files.append(path)
    lines = [
        '# Session Digest',
        '',
        f'Generated: {utc_now()}',
        '',
        '## Session Goal',
        '',
        state.get('goal') or 'No active session goal.',
        '',
        '## Current Status',
        '',
        f'- Status: {state.get("status") or meta.get("status") or "unknown"}',
        f'- Step: {state.get("current_step", 0)} / {state.get("max_steps", 0)}',
        f'- Resume available: {state.get("resume_available", True)}',
        '',
        '## What Changed',
        '',
    ]
    lines.extend(f'- {path}' for path in changed_files) if changed_files else lines.append(
        '- No file changes recorded yet.'
    )
    lines.extend(['', '## Completed Actions', ''])
    completed = [item for item in steps if item.get('outcome') in {'delivered', 'dry_run_only'}]
    if completed:
        for item in completed[-8:]:
            lines.append(f'- {item.get("title") or item.get("action_id")}: {item.get("outcome")}')
    else:
        lines.append('- No completed actions yet.')
    lines.extend(['', '## Current / Next Action', ''])
    lines.append(f'- Current: {state.get("current_action_id") or "not available"}')
    lines.append(f'- Next: {next_action.get("title") or state.get("next_action_id") or "not available"}')
    lines.extend(['', '## Attention Required', ''])
    if state.get('attention_required') or attention:
        lines.append(f'- Reason: {state.get("pause_reason") or attention.get("reason") or "review required"}')
        lines.append(
            f'- Suggested next step: {attention.get("suggested_next_step") or "Review and continue when ready."}'
        )
    else:
        lines.append('- No attention needed right now.')
    lines.extend(['', '## Checkpoints / Undo', ''])
    if checkpoint:
        lines.append(f'- Last checkpoint: {checkpoint.get("checkpoint_id")}')
        lines.append(f'- Undo available: {checkpoint.get("undo_available", False)}')
    else:
        lines.append('- No checkpoint available yet.')
    lines.extend(['', '## Project Progress', ''])
    lines.append(f'- Completed steps: {state.get("completed_steps", 0)}')
    lines.append(f'- Failed steps: {state.get("failed_steps", 0)}')
    lines.extend(
        ['', '## Suggested Commands', '', '- agent continue', '- agent stop', '- agent undo', '- agent cockpit', '']
    )
    path = session_digest_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(str(item) for item in lines), encoding='utf-8')
    return {'status': 'ok', 'digest': str(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a human-readable session digest.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    payload = generate_digest(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
