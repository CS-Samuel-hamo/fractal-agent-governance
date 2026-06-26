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


def _version_path(out_dir: Path, version: int) -> Path:
    return out_dir / 'history' / f'v{version}.json'


def _next_version(out_dir: Path) -> int:
    history_dir = out_dir / 'history'
    history_dir.mkdir(parents=True, exist_ok=True)
    existing = [int(p.stem[1:]) for p in history_dir.glob('v*.json') if p.stem[1:].isdigit()]
    return (max(existing) if existing else 0) + 1


def _changelog_entry(current: dict[str, Any], previous: dict[str, Any] | None) -> list[str]:
    """Compute a human-readable list of changes between two map versions."""
    entries: list[str] = []
    if previous is None:
        return ['initial map build']
    prev_modules = {m.get('module_id'): m for m in previous.get('modules') or []}
    curr_modules = {m.get('module_id'): m for m in current.get('modules') or []}
    for mid, mod in curr_modules.items():
        if mid not in prev_modules:
            entries.append(f'module added: {mod.get("name")}')
        elif prev_modules[mid].get('status') != mod.get('status'):
            entries.append(f'module {mod.get("name")}: {prev_modules[mid].get("status")} → {mod.get("status")}')
    prev_risks = {(r.get('description'), r.get('severity')) for r in previous.get('risks') or []}
    curr_risks = {(r.get('description'), r.get('severity')) for r in current.get('risks') or []}
    for risk, sev in curr_risks - prev_risks:
        entries.append(f'risk added: [{sev}] {risk[:60]}')
    prev_count = len(previous.get('next_actions') or [])
    curr_count = len(current.get('next_actions') or [])
    if curr_count != prev_count:
        entries.append(f'next_actions: {prev_count} → {curr_count}')
    return entries if entries else ['minor update']


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

    # ── Knowledge graph accumulation (方案 B) ─────────────────────────────
    # Track hot modules (frequently changed across sessions)
    hot_modules = current.setdefault('_hot_modules', {})
    for path in changed:
        seg = path.split('/')[0]
        if seg:
            hot_modules[seg] = hot_modules.get(seg, 0) + 1
    current['_hot_modules'] = dict(sorted(hot_modules.items(), key=lambda x: -x[1])[:20])

    # Track failure patterns (verdicts that aren't COMPLETED)
    failures = current.setdefault('_failure_patterns', [])
    if verdict not in {'COMPLETED', 'DRY_RUN_COMPLETE', ''}:
        failures.append(
            {
                'verdict': verdict,
                'run_id': run_id,
                'files': changed[:10],
                'at': now,
            }
        )
    current['_failure_patterns'] = failures[-20:]  # keep last 20

    # Track change frequency per file
    file_stats = current.setdefault('_file_stats', {})
    for path in changed:
        file_stats[path] = file_stats.get(path, 0) + 1
    current['_file_stats'] = dict(sorted(file_stats.items(), key=lambda x: -x[1])[:50])
    # ── End knowledge graph accumulation ──────────────────────────────────

    if action:
        action_id = str(action.get('action_id') or action.get('selected_action_id') or '')
        for item in current.get('next_actions') or []:
            if item.get('action_id') == action_id:
                item['last_result'] = verdict or 'unknown'
                item['last_run_id'] = run_id
                item['last_updated'] = now

    # Versioning: save previous version to history
    version = _next_version(out_dir)
    previous = load_json(out_dir / 'project_map.json') or None
    changelog = _changelog_entry(current, previous)
    current['_version'] = version
    current['_changelog'] = changelog
    current['_updated_by'] = run_id or 'manual'
    current['last_updated'] = now

    # Write versioned history
    if previous:
        vpath = _version_path(out_dir, version)
        vpath.parent.mkdir(parents=True, exist_ok=True)
        write_json(vpath, previous)

    # Write current
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
