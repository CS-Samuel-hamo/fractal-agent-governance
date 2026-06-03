#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from check_codex_worker_concurrency import build_contract, git_root, load_json, safe_name, write_json  # noqa: E402


def utc_now() -> str:
    import datetime

    return datetime.datetime.utcnow().isoformat() + 'Z'


def dispatcher_command(args, repo_root: Path, parent_task_id: str, leaf: dict, worker_log_dir: Path) -> list[str]:
    task_id = str(leaf['task_id'])
    cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'run_ai_native_task.py'),
        '--run-id',
        args.run_id,
        '--task-id',
        task_id,
        '--workspace',
        str(repo_root),
        '--objective',
        str(leaf.get('objective') or ''),
        '--governance-level',
        str(int(leaf.get('recommended_governance_level') or 1)),
        '--worktree-root',
        str(repo_root / '.zoo-agent' / 'worktrees' / safe_name(args.run_id) / 'parallel' / safe_name(parent_task_id) / safe_name(task_id)),
        '--sandbox',
        args.sandbox,
        '--timeout-seconds',
        str(args.timeout_seconds),
        '--test-timeout-seconds',
        str(args.test_timeout_seconds),
        '--max-retries',
        str(args.max_retries),
    ]
    if args.start_point:
        cmd += ['--start-point', args.start_point]
    if args.goal_id:
        cmd += ['--goal-id', args.goal_id]
    if args.profile:
        cmd += ['--profile', args.profile]
    codex_home = args.codex_home
    if args.worker_codex_home_root:
        worker_home = Path(args.worker_codex_home_root).resolve() / safe_name(args.run_id) / safe_name(parent_task_id) / safe_name(task_id)
        worker_home.mkdir(parents=True, exist_ok=True)
        codex_home = str(worker_home)
    if codex_home:
        cmd += ['--codex-home', codex_home]
    if args.full_prompt:
        cmd += ['--full-prompt']
    if args.discard_failed_worktree:
        cmd += ['--discard-failed-worktree']
    if args.ephemeral:
        cmd += ['--ephemeral']
    if args.json_events:
        cmd += ['--json-events']
    if args.worker_dry_run:
        cmd += ['--dry-run']

    for pattern in leaf.get('allowed_files') or []:
        cmd += ['--allowed-file', str(pattern)]
    for pattern in leaf.get('denied_files') or []:
        cmd += ['--denied-file', str(pattern)]
    for command in leaf.get('test_commands') or []:
        cmd += ['--test-command', str(command)]

    write_json(worker_log_dir / 'dispatcher-command.json', {'command': cmd})
    return cmd


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def lock_owner(run_id: str, parent_task_id: str, task_id: str) -> str:
    return f'{safe_name(run_id)}:{safe_name(parent_task_id)}:{safe_name(task_id)}'


def run_lock_command(args, repo_root: Path, item: dict, action: str) -> dict:
    if args.skip_global_locks:
        return {'returncode': 0, 'stdout': '', 'stderr': '', 'skipped': True}
    keys = [str(key) for key in item.get('conflict_keys') or [] if str(key)]
    if not keys:
        return {'returncode': 20, 'stdout': '', 'stderr': 'missing conflict keys for global lock operation'}
    cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'manage_resource_locks.py'),
        '--workspace',
        str(repo_root),
        '--run-id',
        args.run_id,
        '--owner',
        lock_owner(args.run_id, item.get('parent_task_id') or 'parent', item['task_id']),
    ]
    if action == 'acquire':
        cmd += ['--acquire', '--ttl-seconds', str(args.lock_ttl_seconds)]
    elif action == 'release':
        cmd += ['--release']
    else:
        raise ValueError(action)
    for key in keys:
        cmd += ['--conflict-key', key]
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr, 'command': cmd}


def collect_worker_report(repo_root: Path, run_id: str, task_id: str) -> dict:
    candidates = [
        repo_root / '.zoo-agent' / 'runs' / run_id / 'optimistic-runs' / f'{safe_name(task_id)}.json',
        repo_root / '.zoo-agent' / 'runs' / run_id / 'dispatcher-runs' / f'{safe_name(task_id)}.json',
    ]
    for path in candidates:
        payload = load_json(path)
        if payload:
            payload['_path'] = str(path)
            return payload
    return {}


def worker_summary(repo_root: Path, run_id: str, item: dict) -> dict:
    task_id = item['task_id']
    report = collect_worker_report(repo_root, run_id, task_id)
    status = report.get('status') or item.get('status') or 'missing_report'
    attempt = {}
    attempts = report.get('attempts') if isinstance(report.get('attempts'), list) else []
    if attempts:
        attempt = attempts[-1] if isinstance(attempts[-1], dict) else {}
    collected = attempt.get('collected_result') if isinstance(attempt.get('collected_result'), dict) else {}
    return {
        'task_id': task_id,
        'status': status,
        'report_path': report.get('_path', ''),
        'worktree': attempt.get('worktree', ''),
        'branch': attempt.get('branch', ''),
        'changed_files': collected.get('git_diff_name_only') or [],
        'scope_status': (collected.get('scope_guard') or {}).get('status', 'unknown') if collected else 'unknown',
    }


def update_merge_queue(repo_root: Path, run_id: str, parent_task_id: str, workers: list[dict]) -> dict:
    candidates = [item for item in workers if item.get('status') in {'merge_candidate', 'merge_candidate_partial'}]
    payload = {
        'schema_version': '1.0',
        'generated_by': 'run_codex_parallel_workers.py',
        'generated_at': utc_now(),
        'queue_status': 'record_only_parallel_candidates_not_processable',
        'parent_task_id': parent_task_id,
        'readiness_flags': {
            'approved_for_merge': False,
            'approved_for_deploy': False,
            'approved_for_release': False,
            'merge_queue_processing_authorized': False,
        },
        'candidates': candidates,
        'blockers': [
            'Parallel worker results require reviewer and integrator gates before processing.',
            'Parent aggregation must be reviewed before merge.',
        ],
    }
    write_json(repo_root / '.zoo-agent' / 'runs' / run_id / 'merge-queue.json', payload)
    return payload


def update_parent_aggregation(repo_root: Path, run_id: str, parent_task_id: str, workers: list[dict]) -> dict:
    payload = {
        'schema_version': '1.0',
        'generated_by': 'run_codex_parallel_workers.py',
        'generated_at': utc_now(),
        'parent_task_id': parent_task_id,
        'status': 'parallel_leaf_results_recorded',
        'worker_status_counts': {},
        'workers': workers,
        'next_phase_decision': {
            'status': 'review_required',
            'message': 'Review each leaf result, then authorize merge queue processing if appropriate.',
        },
    }
    for item in workers:
        status = item.get('status', 'unknown')
        payload['worker_status_counts'][status] = payload['worker_status_counts'].get(status, 0) + 1
    write_json(repo_root / '.zoo-agent' / 'runs' / run_id / 'parent-aggregation.json', payload)
    return payload


def refresh_summary(repo_root: Path, run_id: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'summarize_ai_native_run.py'), '--run-id', run_id, '--workspace', str(repo_root)],
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}


def run_workers(args, repo_root: Path, contract: dict, output_dir: Path) -> list[dict]:
    pending = list(contract['branch_schedule'])
    running: list[dict] = []
    completed: list[dict] = []
    max_workers = max(1, int(args.max_workers))

    while pending or running:
        while pending and len(running) < max_workers:
            item = pending.pop(0)
            leaf = load_json(Path(item['leaf_path']))
            task_id = item['task_id']
            worker_log_dir = output_dir / safe_name(task_id)
            lock_result = run_lock_command(args, repo_root, item, 'acquire')
            write_json(worker_log_dir / 'resource-lock-acquire.json', lock_result)
            if lock_result.get('returncode') != 0:
                result = {
                    **item,
                    'returncode': lock_result.get('returncode', 20),
                    'elapsed_seconds': 0,
                    'status': 'blocked_by_global_resource_lock',
                    'resource_lock_acquire': str(worker_log_dir / 'resource-lock-acquire.json'),
                }
                write_json(worker_log_dir / 'worker-result.json', result)
                completed.append(result)
                continue
            cmd = dispatcher_command(args, repo_root, contract['parent_task_id'], leaf, worker_log_dir)
            started = time.monotonic()
            proc = subprocess.Popen(
                cmd,
                cwd=ROOT,
                text=True,
                encoding='utf-8',
                errors='replace',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            running.append({'item': item, 'proc': proc, 'started': started, 'worker_log_dir': worker_log_dir})

        still_running = []
        for entry in running:
            proc = entry['proc']
            if proc.poll() is None:
                still_running.append(entry)
                continue
            stdout, stderr = proc.communicate()
            item = entry['item']
            log_dir = entry['worker_log_dir']
            write_text(log_dir / 'dispatcher-stdout.txt', stdout or '')
            write_text(log_dir / 'dispatcher-stderr.txt', stderr or '')
            result = {
                **item,
                'returncode': proc.returncode,
                'elapsed_seconds': round(time.monotonic() - entry['started'], 3),
                'stdout_path': str(log_dir / 'dispatcher-stdout.txt'),
                'stderr_path': str(log_dir / 'dispatcher-stderr.txt'),
            }
            release_result = run_lock_command(args, repo_root, item, 'release')
            write_json(log_dir / 'resource-lock-release.json', release_result)
            result['resource_lock_release'] = str(log_dir / 'resource-lock-release.json')
            write_json(log_dir / 'worker-result.json', result)
            completed.append(result)
        running = still_running
        if running and not pending:
            time.sleep(0.2)
        elif running:
            time.sleep(0.1)
    return completed


def main() -> int:
    ap = argparse.ArgumentParser(description='Run safe Codex leaf workers concurrently through the Zoo dispatcher.')
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--leaf-index', required=True)
    ap.add_argument('--output-dir', default='')
    ap.add_argument('--max-workers', type=int, default=2)
    ap.add_argument('--goal-id', default='')
    ap.add_argument('--start-point', default='HEAD')
    ap.add_argument('--sandbox', default='workspace-write', choices=['read-only', 'workspace-write', 'danger-full-access'])
    ap.add_argument('--profile', default='')
    ap.add_argument('--codex-home', default='')
    ap.add_argument('--worker-codex-home-root', default='')
    ap.add_argument('--timeout-seconds', type=int, default=360)
    ap.add_argument('--test-timeout-seconds', type=int, default=0)
    ap.add_argument('--max-retries', type=int, default=0)
    ap.add_argument('--full-prompt', action='store_true')
    ap.add_argument('--discard-failed-worktree', action='store_true')
    ap.add_argument('--ephemeral', action='store_true')
    ap.add_argument('--json-events', action='store_true')
    ap.add_argument('--allow-planned', action='store_true')
    ap.add_argument('--skip-global-locks', action='store_true', help='Do not acquire .zoo-agent/locks active resource locks before launching leaves.')
    ap.add_argument('--lock-ttl-seconds', type=int, default=7200)
    ap.add_argument('--worker-dry-run', action='store_true', help='Launch each leaf dispatcher with --dry-run.')
    ap.add_argument('--dry-run', action='store_true', help='Only write schedule and resource locks; do not launch workers.')
    args = ap.parse_args()

    repo_root = git_root(Path(args.workspace).resolve())
    leaf_index = Path(args.leaf_index).resolve()
    contract = build_contract(repo_root, args.run_id, leaf_index, max_workers=args.max_workers, allow_planned=args.allow_planned)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else repo_root / '.zoo-agent' / 'runs' / args.run_id / 'parallel-workers' / safe_name(contract['parent_task_id'])
    write_json(output_dir / 'concurrency-check.json', contract)
    write_json(output_dir / 'resource-locks.json', {'resource_locks': contract['resource_locks'], 'status': contract['status'], 'blockers': contract['blockers']})
    write_json(output_dir / 'branch-schedule.json', {'branch_schedule': contract['branch_schedule'], 'status': contract['status'], 'max_workers': contract['max_workers']})

    report = {
        'schema_version': '1.0',
        'generated_by': 'run_codex_parallel_workers.py',
        'generated_at': utc_now(),
        'run_id': args.run_id,
        'parent_task_id': contract['parent_task_id'],
        'leaf_index': str(leaf_index),
        'output_dir': str(output_dir),
        'max_workers': args.max_workers,
        'worker_dry_run': args.worker_dry_run,
        'dry_run': args.dry_run,
        'concurrency_check': contract,
        'status': 'blocked' if contract['status'] != 'pass' else ('dry_run' if args.dry_run else 'running'),
    }
    write_json(output_dir / 'parallel-run.json', report)
    if contract['status'] != 'pass':
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 20
    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    completed = run_workers(args, repo_root, contract, output_dir)
    workers = [worker_summary(repo_root, args.run_id, item) for item in completed]
    merge_queue = update_merge_queue(repo_root, args.run_id, contract['parent_task_id'], workers)
    parent_aggregation = update_parent_aggregation(repo_root, args.run_id, contract['parent_task_id'], workers)
    summary_refresh = refresh_summary(repo_root, args.run_id)
    failures = [item for item in completed if item.get('returncode') != 0]
    report.update(
        {
            'status': 'completed_with_failures' if failures else 'completed',
            'completed_workers': completed,
            'workers': workers,
            'merge_queue': merge_queue,
            'parent_aggregation': parent_aggregation,
            'summary_refresh': summary_refresh,
            'ended_at': utc_now(),
        }
    )
    write_json(output_dir / 'parallel-run.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 10


if __name__ == '__main__':
    raise SystemExit(main())
