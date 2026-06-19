#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        'command': [str(item) for item in command],
        'cwd': str(cwd),
        'returncode': proc.returncode,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def ensure_risk_register(project: Path, run_id: str) -> dict[str, Any]:
    path = project / '.zoo-agent' / 'runs' / run_id / 'risk-register.json'
    payload = load_json(path)
    if payload:
        return {'status': 'existing', 'path': str(path), 'risk_register': payload}
    payload = {
        'schema_version': '1.0',
        'generated_by': 'runtime_review.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'workspace': str(project),
        'open_risk_count': 0,
        'risks': [],
    }
    write_json(path, payload)
    return {'status': 'initialized_empty', 'path': str(path), 'risk_register': payload}


def merge_queue_findings(run_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    queue = load_json(run_dir / 'merge-queue.json')
    if not queue:
        return blockers, warnings
    candidate_count = len(queue.get('candidates') or []) if isinstance(queue.get('candidates'), list) else 0
    queue_status = str(queue.get('queue_status') or '')
    if candidate_count and queue_status == 'record_only_parallel_candidates_not_processable':
        blockers.append(
            {
                'id': 'merge_queue_record_only',
                'message': 'Merge candidates exist but the merge queue is record-only and not processable.',
            }
        )
    flags = queue.get('readiness_flags') if isinstance(queue.get('readiness_flags'), dict) else {}
    if flags.get('approved_for_deploy') or flags.get('approved_for_release'):
        warnings.append({'id': 'unexpected_deploy_release_flag', 'message': 'Review evidence should not approve deploy or release.'})
    return blockers, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description='Run CLI-first runtime review closure checks for a run.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--governance-only', action='store_true')
    parser.add_argument('--allow-missing-tests', action='store_true')
    parser.add_argument('--allow-open-risks', action='store_true')
    parser.add_argument('--allow-task-board-warnings', action='store_true')
    parser.add_argument('--allow-project-readiness-blocks', action='store_true')
    parser.add_argument('--allow-architecture-blocks', action='store_true')
    parser.add_argument('--accept-parent-aggregation', action='store_true')
    args = parser.parse_args()

    project = project_root(args.workspace)
    run_dir = project / '.zoo-agent' / 'runs' / args.run_id
    risk = ensure_risk_register(project, args.run_id)

    task_board_cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'check_task_board_consistency.py'),
        '--workspace',
        str(project),
        '--run-id',
        args.run_id,
    ]
    task_board = run_command(task_board_cmd, ROOT)

    quality_cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'run_quality_gate.py'),
        '--workspace',
        str(project),
        '--run-id',
        args.run_id,
    ]
    if args.governance_only:
        quality_cmd.append('--governance-only')
    for enabled, flag in [
        (args.allow_missing_tests, '--allow-missing-tests'),
        (args.allow_open_risks, '--allow-open-risks'),
        (args.allow_task_board_warnings, '--allow-task-board-warnings'),
        (args.allow_project_readiness_blocks, '--allow-project-readiness-blocks'),
        (args.allow_architecture_blocks, '--allow-architecture-blocks'),
        (args.accept_parent_aggregation, '--accept-parent-aggregation'),
    ]:
        if enabled:
            quality_cmd.append(flag)
    quality_gate = run_command(quality_cmd, ROOT)

    blockers, warnings = merge_queue_findings(run_dir)
    quality_payload = load_json(run_dir / 'quality-gate.json')
    task_board_payload = load_json(run_dir / 'task-board-consistency.json')
    if quality_payload.get('gate_status') == 'blocked':
        blockers.extend(quality_payload.get('blockers') or [])
    elif quality_payload.get('gate_status') == 'needs_review':
        warnings.extend(quality_payload.get('warnings') or [])
    if task_board_payload.get('status') == 'warnings' and not args.allow_task_board_warnings:
        blockers.append({'id': 'task_board_consistency_warnings', 'message': 'Task-board consistency warnings remain.'})

    status = 'blocked' if blockers else ('needs_review' if warnings else 'pass')
    report = {
        'schema_version': '1.0',
        'generated_by': 'runtime_review.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'run_id': args.run_id,
        'status': status,
        'risk_register': risk,
        'task_board_consistency': task_board,
        'quality_gate': quality_gate,
        'merge_queue_readiness': {
            'blockers': blockers,
            'warnings': warnings,
            'merge_queue_path': str(run_dir / 'merge-queue.json'),
        },
        'safety': {
            'review_is_not_merge_authorization': True,
            'deploy_release_authorized': False,
            'durable_state_authorized': False,
        },
    }
    write_json(run_dir / 'runtime-review.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == 'pass' else (10 if status == 'needs_review' else 20)


if __name__ == '__main__':
    raise SystemExit(main())
