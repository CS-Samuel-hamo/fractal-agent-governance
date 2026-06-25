#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


def changed_files_from_execution(execution: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for leaf in execution.get('leaf_results') or []:
        for item in leaf.get('business_changed_files') or leaf.get('diff') or []:
            normalized = str(item).replace('\\', '/')
            if normalized and normalized not in changed:
                changed.append(normalized)
    return changed


def build_progress_summary(
    project: Path, *, action: dict[str, Any], execution: dict[str, Any], final_result: dict[str, Any], mode: str
) -> dict[str, Any]:
    changed = changed_files_from_execution(execution)
    verdict = str(final_result.get('final_verdict') or '')
    if verdict in {'COMPLETED', 'DRY_RUN_COMPLETE'}:
        status = 'done' if mode != 'preview' else 'preview_ready'
    elif verdict in {'NO_DELIVERY', 'BLOCKED'}:
        status = 'needs_attention'
    else:
        status = 'doing'
    payload = {
        'schema_version': '1.0',
        'generated_by': 'progress_summary_generator.py',
        'generated_at': utc_now(),
        'status': status,
        'mode': mode,
        'action_id': action.get('selected_action_id') or action.get('action_id') or '',
        'title': action.get('title') or '',
        'changed_files': changed,
        'why': [action.get('reason') or action.get('why_now') or 'Selected from the project map.'],
        'project_progress': [action.get('expected_project_progress') or 'Project map updated.'],
        'undo': 'agent undo',
        'result': verdict,
    }
    write_json(project / '.zoo-agent' / 'autopilot' / 'progress.json', payload)
    return payload


def render_user_summary(summary: dict[str, Any]) -> str:
    if summary.get('status') == 'needs_attention':
        return (
            'Needs attention.\nReason:\n* '
            + str(summary.get('result') or 'review required')
            + '\n\nSuggested next step:\n* Review the latest result and run agent continue when ready.'
        )
    heading = 'Preview ready.' if summary.get('status') == 'preview_ready' else 'Done.'
    changed = summary.get('changed_files') or []
    changed_lines = '\n'.join(f'* {item}' for item in changed) if changed else '* No business files changed'
    why_lines = '\n'.join(f'* {item}' for item in summary.get('why') or [])
    progress_lines = '\n'.join(f'* {item}' for item in summary.get('project_progress') or [])
    return f'{heading}\nChanged:\n{changed_lines}\n\nWhy:\n{why_lines}\n\nProject progress:\n{progress_lines}\n\nUndo:\nagent undo'


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a concise user progress summary.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--action', required=True)
    parser.add_argument('--execution-result', required=True)
    parser.add_argument('--final-result', required=True)
    parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='standard')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_progress_summary(
        project,
        action=load_json(Path(args.action).resolve()),
        execution=load_json(Path(args.execution_result).resolve()),
        final_result=load_json(Path(args.final_result).resolve()),
        mode=args.mode,
    )
    print(render_user_summary(payload))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
