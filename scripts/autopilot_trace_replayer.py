#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root


def _action_by_id(project_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get('action_id') or ''): item
        for item in project_map.get('next_actions') or []
        if isinstance(item, dict)
    }


def render_replay(trace: dict[str, Any], project_map: dict[str, Any], state: dict[str, Any]) -> str:
    actions = _action_by_id(project_map)
    lines = [
        '# Autopilot Replay',
        '',
        f'- main_goal: {project_map.get("main_goal") or state.get("main_goal") or "unknown"}',
        f'- project_state: {state.get("status") or "unknown"}',
        '',
    ]
    if not trace.get('runs'):
        lines += ['No autopilot runs were recorded.', '']
        return '\n'.join(lines)
    for run in trace.get('runs') or []:
        action = actions.get(str(run.get('selected_action_id') or ''), {})
        evidence = action.get('evidence') or []
        lines += [
            f'## Step {run.get("step")}: {run.get("selected_action")}',
            '',
            f'- source: {run.get("source")}',
            f'- why selected: {action.get("why_now") or "not recorded"}',
            f'- evidence: {", ".join(str(item.get("path") or item.get("summary") or "") for item in evidence[:3]) or "missing"}',
            f'- before state: checkpoint_created={str(run.get("checkpoint_created")).lower()}',
            f'- after state: map_updated={str(run.get("map_updated")).lower()}, progress_summary_created={str(run.get("progress_summary_created")).lower()}',
            f'- changed_files: {", ".join(str(item) for item in run.get("changed_files") or []) or "none"}',
            f'- goal progress: {action.get("expected_impact") or "not recorded"}',
            f'- outcome: {run.get("outcome")}',
        ]
        if run.get('attention_required'):
            lines.append('- stop reason: attention required before continuing')
        lines.append('')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Replay an autopilot dogfood trace.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--trace', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    trace_path = (
        Path(args.trace).resolve() if args.trace else project / '.zoo-agent' / 'dogfood' / 'autopilot_trace.json'
    )
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'dogfood' / 'autopilot_replay.md'
    text = render_replay(
        load_json(trace_path),
        load_json(project / '.zoo-agent' / 'map' / 'project_map.json'),
        load_json(project / '.zoo-agent' / 'map' / 'project_state.json'),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding='utf-8')
    print(json.dumps({'status': 'ok', 'autopilot_replay': str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
