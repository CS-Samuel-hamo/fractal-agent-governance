#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_map_builder import build_project_map, render_markdown
from project_map_schema import map_dir
from runtime_common import load_json, project_root, utc_now, write_json


def _changed_files(execution_result: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for leaf in execution_result.get('leaf_results') or []:
        delivery = leaf.get('delivery') if isinstance(leaf.get('delivery'), dict) else {}
        for path in (
            leaf.get('business_changed_files')
            or delivery.get('business_changed_files')
            or leaf.get('changed_files')
            or leaf.get('diff')
            or []
        ):
            normalized = str(path).replace('\\', '/')
            if normalized and normalized not in changed:
                changed.append(normalized)
    return changed


def update_project_map(
    project: Path,
    *,
    run_id: str = '',
    action: dict[str, Any] | None = None,
    execution_result: dict[str, Any] | None = None,
    final_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out_dir = map_dir(project)
    current = load_json(out_dir / 'project_map.json')
    if not current:
        current, state, evidence = build_project_map(project)
        write_json(out_dir / 'project_state.json', state)
        write_json(out_dir / 'map_evidence.json', evidence)
    changed = _changed_files(execution_result or {})
    verdict = str((final_result or {}).get('final_verdict') or '')
    now = utc_now()
    update_evidence = {
        'kind': 'run_result',
        'path': run_id,
        'summary': f'Run {run_id or "unknown"} finished with {verdict or "unknown"}.',
        'confidence': 0.75 if verdict in {'COMPLETED', 'DRY_RUN_COMPLETE'} else 0.45,
    }
    for module in current.get('modules') or []:
        key_files = [str(item) for item in module.get('key_files') or []]
        if changed and any(
            path == item or path.startswith(item.rstrip('/') + '/') for path in changed for item in key_files
        ):
            module['status'] = 'working' if verdict != 'COMPLETED' else 'complete'
            module.setdefault('evidence', []).append(update_evidence)
            module['confidence'] = min(1.0, round(float(module.get('confidence') or 0.5) + 0.05, 3))
    if action:
        action_id = str(action.get('action_id') or action.get('selected_action_id') or '')
        for item in current.get('next_actions') or []:
            if item.get('action_id') == action_id:
                item['last_result'] = verdict or 'unknown'
                item['last_run_id'] = run_id
                item['last_updated'] = now
    current['last_updated'] = now
    write_json(out_dir / 'project_map.json', current)
    md = out_dir / 'project_map.md'
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(render_markdown(current), encoding='utf-8')
    state = load_json(out_dir / 'project_state.json')
    state.update(
        {
            'status': 'working' if verdict not in {'COMPLETED', 'DRY_RUN_COMPLETE'} else 'mapped',
            'last_action': (action or {}).get('title') or (action or {}).get('selected_action_id') or '',
            'last_result': verdict or state.get('last_result', ''),
            'last_updated': now,
        }
    )
    if verdict == 'COMPLETED':
        state['progress'] = '20%'
    write_json(out_dir / 'project_state.json', state)
    return {'project_map': current, 'project_state': state, 'changed_files': changed}


def main() -> int:
    parser = argparse.ArgumentParser(description='Update project map after a run.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--selected-action', default='')
    parser.add_argument('--execution-result', default='')
    parser.add_argument('--final-result', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = update_project_map(
        project,
        run_id=args.run_id,
        action=load_json(Path(args.selected_action).resolve()) if args.selected_action else {},
        execution_result=load_json(Path(args.execution_result).resolve()) if args.execution_result else {},
        final_result=load_json(Path(args.final_result).resolve()) if args.final_result else {},
    )
    print(json.dumps({'status': 'ok', 'changed_files': payload['changed_files']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
