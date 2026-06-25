#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, safe_name, utc_now, write_json


def latest_run_id(project: Path) -> str:
    runs_dir = project / '.zoo-agent' / 'runs'
    if not runs_dir.exists():
        return ''
    candidates = [path for path in runs_dir.iterdir() if path.is_dir()]
    if not candidates:
        return ''
    latest = sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]
    return latest.name


def load_cli_reports(run_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((run_dir / 'cli-runtime').glob('*.json')):
        payload = load_json(path)
        if payload:
            rows.append(
                {
                    'task_id': payload.get('task_id', path.stem),
                    'selected_path': payload.get('selected_path', ''),
                    'classification_path': (payload.get('classification') or {}).get('path', ''),
                    'execution_status': (payload.get('execution') or {}).get('status', ''),
                    'goal_alignment_status': (payload.get('goal_alignment') or {}).get('status', ''),
                    'report_path': str(path),
                }
            )
    return rows


def load_goal_alignment(run_dir: Path) -> dict[str, int]:
    counts = {'pass': 0, 'needs_review': 0, 'blocked': 0, 'missing': 0}
    alignment_dir = run_dir / 'goal-alignment'
    if not alignment_dir.exists():
        counts['missing'] = 1
        return counts
    for path in alignment_dir.glob('*.json'):
        status = str(load_json(path).get('status') or 'missing')
        counts[status] = counts.get(status, 0) + 1
    if not any(counts.values()):
        counts['missing'] = 1
    return counts


def load_worktrees(project: Path, run_id: str) -> list[str]:
    root = project / '.zoo-agent' / 'worktrees' / safe_name(run_id)
    if not root.exists():
        return []
    return [str(path) for path in sorted(root.rglob('*')) if path.is_dir() and (path / '.git').exists()]


def runtime_status(project: Path, run_id: str = '') -> dict[str, Any]:
    run_id = run_id or latest_run_id(project)
    run_dir = project / '.zoo-agent' / 'runs' / run_id if run_id else project / '.zoo-agent' / 'runs'
    quality_gate = load_json(run_dir / 'quality-gate.json') if run_id else {}
    risk_register = load_json(run_dir / 'risk-register.json') if run_id else {}
    merge_queue = load_json(run_dir / 'merge-queue.json') if run_id else {}
    task_board = load_json(run_dir / 'task-board-consistency.json') if run_id else {}
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if run_id and not run_dir.exists():
        blockers.append({'id': 'run_missing', 'message': f'Run directory does not exist: {run_dir}'})
    if quality_gate.get('gate_status') == 'blocked':
        blockers.append({'id': 'quality_gate_blocked', 'message': 'quality-gate.json is blocked.'})
    elif quality_gate.get('gate_status') == 'needs_review':
        warnings.append({'id': 'quality_gate_needs_review', 'message': 'quality-gate.json needs review.'})
    if int(risk_register.get('open_risk_count') or 0):
        blockers.append(
            {'id': 'open_run_risks', 'message': 'Open run risks remain.', 'count': risk_register.get('open_risk_count')}
        )
    if merge_queue.get('queue_status') == 'record_only_parallel_candidates_not_processable':
        warnings.append(
            {
                'id': 'record_only_merge_queue',
                'message': 'Parallel merge queue is record-only and not merge authorization.',
            }
        )
    if task_board.get('status') == 'warnings':
        warnings.append({'id': 'task_board_warnings', 'message': 'Task-board consistency warnings remain.'})

    status = 'blocked' if blockers else ('needs_review' if warnings else 'ok')
    return {
        'schema_version': '1.0',
        'generated_by': 'runtime_status.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'status': status,
        'run_id': run_id,
        'runtime_marker': load_json(project / '.zoo-agent' / 'runtime-v4.json'),
        'goal_state': load_json(project / '.zoo-agent' / 'goal_state.json'),
        'current_run': load_json(project / '.zoo-agent' / 'current-run.json'),
        'loop_state': load_json(project / '.zoo-agent' / 'loop_state.json'),
        'code_standards': {
            'exists': (project / '.zoo-agent' / 'code-standards.json').exists(),
            'path': str(project / '.zoo-agent' / 'code-standards.json'),
        },
        'project_map_alignment': load_json(project / '.zoo-agent' / 'project-map-alignment.json'),
        'metrics': load_json(project / '.zoo-agent' / 'metrics' / 'agent-runtime-v4.json').get('metrics', {}),
        'run': {
            'path': str(run_dir) if run_id else '',
            'cli_reports': load_cli_reports(run_dir) if run_id else [],
            'goal_alignment_counts': load_goal_alignment(run_dir) if run_id else {},
            'worktrees': load_worktrees(project, run_id) if run_id else [],
            'risk_register': risk_register,
            'task_board_consistency': task_board,
            'quality_gate': quality_gate,
            'merge_queue': {
                'queue_status': merge_queue.get('queue_status', 'missing') if merge_queue else 'missing',
                'candidate_count': len(merge_queue.get('candidates') or [])
                if isinstance(merge_queue.get('candidates'), list)
                else 0,
                'readiness_flags': merge_queue.get('readiness_flags', {})
                if isinstance(merge_queue.get('readiness_flags'), dict)
                else {},
            },
        },
        'blockers': blockers,
        'warnings': warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Summarize CLI-first runtime status.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--output', default='')
    parser.add_argument('--no-write', action='store_true')
    args = parser.parse_args()

    project = project_root(args.workspace)
    report = runtime_status(project, args.run_id)
    if args.no_write:
        pass
    elif args.output:
        write_json(Path(args.output).resolve(), report)
    elif report.get('run_id'):
        write_json(project / '.zoo-agent' / 'runs' / str(report['run_id']) / 'runtime-status.json', report)
    else:
        write_json(project / '.zoo-agent' / 'runtime-status.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('status') == 'ok' else (10 if report.get('status') == 'needs_review' else 20)


if __name__ == '__main__':
    raise SystemExit(main())
