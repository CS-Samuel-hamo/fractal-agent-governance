#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def git_root(workspace: Path) -> Path:
    proc = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        cwd=workspace,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or 'workspace is not a git repository')
    return Path(proc.stdout.strip()).resolve()


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def refresh_summary(repo_root: Path, run_id: str) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'summarize_ai_native_run.py'),
            '--run-id',
            run_id,
            '--workspace',
            str(repo_root),
        ],
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    return {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}


def candidates_from_summary(summary: dict) -> list[dict]:
    candidates = []
    for item in summary.get('merge_candidates') or []:
        if isinstance(item, dict):
            candidates.append(item)
    return candidates


def write_markdown(path: Path, payload: dict) -> None:
    lines = [
        f'# Merge Queue Processing: {payload["run_id"]}',
        '',
        f'- status: {payload["status"]}',
        f'- queue_status: {payload["merge_queue"].get("queue_status", "missing")}',
        f'- candidate_count: {len(payload["merge_queue"].get("candidates") or [])}',
        f'- approved_for_merge: {payload["merge_queue"].get("readiness_flags", {}).get("approved_for_merge", False)}',
        '',
        '## Blockers',
        '',
    ]
    if not payload.get('blockers'):
        lines.append('- none')
    else:
        for blocker in payload['blockers']:
            lines.append(f'- {blocker.get("id")}: {blocker.get("message")}')
    lines += ['', '## Serial Integrator Contract', '']
    for item in payload.get('serial_integrator_contract', {}).get('steps', []):
        lines.append(f'- {item}')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser(description='Turn a validated record-only merge queue into a serial integrator queue.')
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument(
        '--authorize', action='store_true', help='Explicitly authorize merge queue processing after quality gate pass.'
    )
    ap.add_argument(
        '--approve-merge-readiness',
        action='store_true',
        help='Record final merge-readiness approval. Does not run git merge.',
    )
    ap.add_argument('--accept-parent-aggregation', action='store_true')
    ap.add_argument('--authorization-note', default='')
    ap.add_argument('--no-refresh-summary', action='store_true')
    args = ap.parse_args()

    repo_root = git_root(Path(args.workspace).resolve())
    run_dir = repo_root / '.zoo-agent' / 'runs' / args.run_id
    queue_path = run_dir / 'merge-queue.json'
    process_path = run_dir / 'merge-queue-processing.json'

    refresh = {'skipped': True}
    if not args.no_refresh_summary:
        refresh = refresh_summary(repo_root, args.run_id)
    summary = load_json(run_dir / 'ai-native-summary.json')
    quality_gate = load_json(run_dir / 'quality-gate.json')
    queue = load_json(queue_path)
    blockers = []

    if quality_gate.get('gate_status') != 'pass':
        blockers.append(
            {'id': 'quality_gate_not_pass', 'message': 'quality-gate.json must pass before queue processing.'}
        )
    q_flags = quality_gate.get('readiness_flags') if isinstance(quality_gate.get('readiness_flags'), dict) else {}
    if not q_flags.get('merge_queue_processing_authorized') and not args.authorize:
        blockers.append(
            {
                'id': 'queue_processing_not_authorized',
                'message': 'Run quality gate with --authorize-merge-queue or pass --authorize here.',
            }
        )
    if args.authorize and not args.authorization_note:
        blockers.append(
            {
                'id': 'missing_authorization_note',
                'message': '--authorization-note is required when --authorize is used.',
            }
        )

    candidates = queue.get('candidates') if isinstance(queue.get('candidates'), list) else []
    if not candidates:
        candidates = candidates_from_summary(summary)
    if not candidates:
        blockers.append(
            {'id': 'missing_merge_candidates', 'message': 'No merge candidates are available for queue processing.'}
        )

    parent = load_json(run_dir / 'parent-aggregation.json')
    parent_decision = parent.get('next_phase_decision') if isinstance(parent.get('next_phase_decision'), dict) else {}
    parent_status = str(parent_decision.get('status') or parent.get('status') or '').lower()
    if parent_status == 'review_required' and not args.accept_parent_aggregation:
        blockers.append(
            {'id': 'parent_aggregation_review_required', 'message': 'Parent aggregation still requires review.'}
        )

    approved_for_merge = bool(args.approve_merge_readiness)
    queue_status = 'blocked'
    if not blockers:
        queue_status = (
            'processable_merge_readiness_approved' if approved_for_merge else 'processable_pending_serial_integrator'
        )

    merged_queue = {
        'schema_version': '1.0',
        'generated_by': 'process_merge_queue.py',
        'generated_at': utc_now(),
        'queue_status': queue_status,
        'run_id': args.run_id,
        'parent_task_id': queue.get('parent_task_id') or parent.get('parent_task_id') or '',
        'readiness_flags': {
            'merge_queue_processing_authorized': not blockers,
            'approved_for_merge': approved_for_merge and not blockers,
            'approved_for_deploy': False,
            'approved_for_release': False,
        },
        'authorization': {
            'authorized': bool(args.authorize or q_flags.get('merge_queue_processing_authorized')) and not blockers,
            'note': args.authorization_note,
            'approved_merge_readiness': approved_for_merge and not blockers,
            'authorized_at': utc_now() if not blockers else '',
        },
        'candidates': candidates,
        'blockers': blockers,
        'source_queue_status': queue.get('queue_status', 'missing'),
        'quality_gate_path': str(run_dir / 'quality-gate.json'),
    }
    write_json(queue_path, merged_queue)

    process_payload = {
        'schema_version': '1.0',
        'generated_by': 'process_merge_queue.py',
        'generated_at': utc_now(),
        'run_id': args.run_id,
        'status': 'ready_for_serial_integrator' if not blockers else 'blocked',
        'workspace': str(repo_root),
        'merge_queue': merged_queue,
        'blockers': blockers,
        'refresh_summary': refresh,
        'serial_integrator_contract': {
            'merge_is_not_executed_by_this_script': True,
            'steps': [
                'Review each candidate diff from its worktree or branch.',
                'Apply candidates one at a time in a clean integration worktree.',
                'Run the relevant test and scope guard set after each candidate.',
                'Refresh quality gate and merge queue evidence after integration.',
                'Do not deploy, release, or mutate durable state from queue processing alone.',
            ],
        },
    }
    write_json(process_path, process_payload)
    write_markdown(process_path.with_suffix('.md'), process_payload)
    print(json.dumps(process_payload, ensure_ascii=False, indent=2))
    return 0 if not blockers else 20


if __name__ == '__main__':
    raise SystemExit(main())
