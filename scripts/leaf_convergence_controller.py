#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import leaf_readiness, load_backend_profile, load_leaf_contracts, project_root
from leaf_resolution_policy import DEFAULT_MAX_REFINEMENTS, leaf_resolution_policy, refinement_count
from runtime_common import load_json, utc_now, write_json


def _leaf_path(project: Path, run_id: str, leaf_id: str) -> Path:
    return project / '.zoo-agent' / 'runs' / run_id / 'leaf-tasks' / f'{leaf_id}.json'


def _resource_path(project: Path, run_id: str, *parts: str) -> Path:
    return project / '.zoo-agent' / 'runs' / run_id / 'leaf-resolution' / Path(*parts)


def _refine_leaf(leaf: dict[str, Any]) -> dict[str, Any]:
    refined = dict(leaf)
    current = refinement_count(leaf)
    resolution = dict(refined.get('resolution') or {})
    resolution['refinement_count'] = current + 1
    resolution['refined_from_leaf_id'] = leaf.get('leaf_id')
    refined['resolution'] = resolution
    refined['generated_by'] = 'leaf_convergence_controller.py'
    refined['refined_at'] = utc_now()
    if not refined.get('acceptance') and refined.get('allowed_files'):
        refined['acceptance'] = [
            f'Bounded change for {refined.get("objective") or refined.get("leaf_id")} is reviewable and satisfies parent criteria.'
        ]
    return refined


def _status_for(action: str) -> str:
    if action == 'execute':
        return 'resolved'
    if action == 'collapse':
        return 'collapsed'
    if action == 'defer':
        return 'deferred'
    if action == 'merge':
        return 'merged'
    return 'stuck'


def _write_leaf_resolution(project: Path, run_id: str, leaf_id: str, payload: dict[str, Any]) -> Path:
    path = _resource_path(project, run_id, 'leaves', f'{leaf_id}.json')
    write_json(path, payload)
    return path


def _record_action_buckets(project: Path, run_id: str, resolutions: list[dict[str, Any]]) -> None:
    backlog = []
    merged = []
    collapsed = []
    execution_queue = []
    for item in resolutions:
        leaf_id = item.get('leaf_id')
        action = item.get('final_resolution')
        if action == 'defer':
            backlog.append({'leaf_id': leaf_id, 'reason': item.get('reason'), 'next_action': item.get('next_action')})
        elif action == 'merge':
            merged.append(
                {
                    'leaf_id': leaf_id,
                    'reason': item.get('reason'),
                    'parent_action': 'parent_aggregation_owns_obligation',
                }
            )
        elif action == 'collapse':
            collapsed.append({'leaf_id': leaf_id, 'reason': item.get('reason'), 'micro_task_allowed': True})
        elif action == 'execute':
            execution_queue.append(
                {'leaf_id': leaf_id, 'reason': item.get('reason'), 'requires_explicit_confirmation': True}
            )
    base = project / '.zoo-agent' / 'runs' / run_id
    write_json(base / 'follow-up-backlog.json', {'run_id': run_id, 'items': backlog})
    write_json(base / 'leaf-merge-to-parent.json', {'run_id': run_id, 'items': merged})
    write_json(base / 'micro-tasks.json', {'run_id': run_id, 'items': collapsed})
    write_json(base / 'leaf-execution-queue.json', {'run_id': run_id, 'items': execution_queue})


def _write_metrics(project: Path, report: dict[str, Any]) -> None:
    total = max(int(report.get('leaf_count') or 0), 1)
    counts = report.get('counts') or {}
    metrics = {
        'schema_version': '1.0',
        'generated_by': 'leaf_convergence_controller.py',
        'updated_at': utc_now(),
        'run_id': report.get('run_id'),
        'leaf_refinement_count': counts.get('refine', 0),
        'leaf_resolution_rate': round((total - counts.get('stuck', 0)) / total, 4),
        'leaf_collapse_rate': round(counts.get('collapse', 0) / total, 4),
        'leaf_defer_rate': round(counts.get('defer', 0) / total, 4),
        'leaf_merge_rate': round(counts.get('merge', 0) / total, 4),
        'convergence_failure_rate': round(counts.get('stuck', 0) / total, 4),
        'codex_execution_from_leaf_rate': round(counts.get('execute', 0) / total, 4),
        'targets': {
            'leaf_resolution_rate': '100%',
            'convergence_failure_rate': '0',
            'infinite_decomposition': '0',
        },
    }
    write_json(project / '.zoo-agent' / 'metrics' / 'leaf-convergence.json', metrics)


def resolve_one_leaf(
    project: Path,
    run_id: str,
    leaf: dict[str, Any],
    *,
    backend: dict[str, Any],
    max_refinements: int = DEFAULT_MAX_REFINEMENTS,
    max_resolution_depth: int = 3,
) -> dict[str, Any]:
    leaf_id = str(leaf.get('leaf_id') or 'leaf')
    current = dict(leaf)
    resolution_path: list[str] = []
    refined_paths: list[str] = []
    loop_detected = False
    final_record: dict[str, Any] | None = None

    for depth in range(max_resolution_depth):
        readiness = leaf_readiness(current, backend)
        record = leaf_resolution_policy(current, readiness, backend_profile=backend, max_refinements=max_refinements)
        action = str(record.get('resolution') or 'blocked')
        resolution_path.append(action)
        if resolution_path.count('refine') > max_refinements:
            loop_detected = True
            final_record = {
                **record,
                'leaf_state': 'blocked',
                'resolution': 'blocked',
                'final': True,
                'reason': 'convergence_failure_refine_loop',
            }
            break
        if action == 'refine':
            current = _refine_leaf(current)
            refined_path = _resource_path(
                project, run_id, 'refined-leaves', f'{leaf_id}-refined-{refinement_count(current)}.json'
            )
            write_json(refined_path, current)
            refined_paths.append(str(refined_path))
            continue
        final_record = record
        break

    if final_record is None:
        loop_detected = True
        final_record = {
            'leaf_id': leaf_id,
            'run_id': run_id,
            'leaf_state': 'blocked',
            'resolution': 'blocked',
            'final': True,
            'reason': 'convergence_failure_max_resolution_depth',
            'readiness_verdict': '',
            'blocking_reasons': ['convergence_failure'],
            'refinement_count': refinement_count(current),
            'max_refinements': max_refinements,
            'next_action': 'human_or_gpt_decision_required',
        }

    action = str(final_record.get('resolution') or 'blocked')
    status = _status_for(action)
    result = {
        'schema_version': '1.0',
        'generated_by': 'leaf_convergence_controller.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'leaf_id': leaf_id,
        'status': status,
        'final_resolution': action,
        'leaf_state': final_record.get('leaf_state'),
        'reason': final_record.get('reason'),
        'readiness_verdict': final_record.get('readiness_verdict'),
        'blocking_reasons': final_record.get('blocking_reasons') or [],
        'resolution_path': resolution_path,
        'refined_leaf_contracts': refined_paths,
        'loop_detected': loop_detected,
        'action_taken': final_record.get('next_action'),
    }

    original_path = Path(str(leaf.get('_path') or _leaf_path(project, run_id, leaf_id)))
    persisted = load_json(original_path)
    if persisted:
        persisted['leaf_state'] = result['leaf_state']
        persisted['final_resolution'] = action
        persisted['resolution_status'] = status
        persisted['resolution_path'] = resolution_path
        persisted['refined_leaf_contracts'] = refined_paths
        persisted['convergence'] = result
        write_json(original_path, persisted)
    _write_leaf_resolution(project, run_id, leaf_id, result)
    return result


def run_leaf_convergence(
    project: Path,
    run_id: str,
    *,
    max_refinements: int = DEFAULT_MAX_REFINEMENTS,
    max_resolution_depth: int = 3,
) -> dict[str, Any]:
    leaves = load_leaf_contracts(project, run_id)
    backend = load_backend_profile(project)
    resolutions = [
        resolve_one_leaf(
            project,
            run_id,
            leaf,
            backend=backend,
            max_refinements=max_refinements,
            max_resolution_depth=max_resolution_depth,
        )
        for leaf in leaves
    ]
    counts = {'execute': 0, 'refine': 0, 'merge': 0, 'defer': 0, 'collapse': 0, 'stuck': 0}
    for item in resolutions:
        action = str(item.get('final_resolution') or 'blocked')
        if action in counts:
            counts[action] += 1
        if item.get('status') == 'stuck':
            counts['stuck'] += 1
        counts['refine'] += list(item.get('resolution_path') or []).count('refine')
    unresolved = [item for item in resolutions if item.get('status') == 'stuck']
    report = {
        'schema_version': '1.0',
        'generated_by': 'leaf_convergence_controller.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'leaf_count': len(leaves),
        'resolutions': resolutions,
        'counts': counts,
        'status': 'convergence_failure' if unresolved else 'resolved',
        'unresolved_leaf_ids': [item.get('leaf_id') for item in unresolved],
        'infinite_decomposition_prevented': True,
    }
    base = project / '.zoo-agent' / 'runs' / run_id
    write_json(base / 'leaf-convergence-report.json', report)
    _record_action_buckets(project, run_id, resolutions)
    _write_metrics(project, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Resolve leaf tasks into execute/refine/merge/defer/collapse outcomes.'
    )
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--max-refinements', type=int, default=DEFAULT_MAX_REFINEMENTS)
    parser.add_argument('--max-resolution-depth', type=int, default=3)
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = run_leaf_convergence(
        project,
        args.run_id,
        max_refinements=args.max_refinements,
        max_resolution_depth=args.max_resolution_depth,
    )
    print(json.dumps({'status': report['status'], 'report': report}, ensure_ascii=True, indent=2))
    return 0 if report.get('status') == 'resolved' else 10


if __name__ == '__main__':
    raise SystemExit(main())
