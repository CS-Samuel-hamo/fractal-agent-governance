#!/usr/bin/env python3
"""Command handler functions for the agent CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from agent_utils import (
    delegate,
    delegate_capture,
    parse_json_output,
    print_json,
    workspace_arg,
)
from runtime_common import project_root


def backend_command(args) -> int:
    command = ['--workspace', workspace_arg(args.workspace)]
    if args.backend_action == 'switch':
        command.extend(['--select', args.name])
    elif args.backend_action == 'health':
        command.append('--health')
    elif args.backend_action == 'list':
        command.append('--list')
    else:
        print(f'Unsupported backend action: {args.backend_action}', file=sys.stderr)
        return 2
    result = delegate_capture('backend_registry.py', command)
    if result.get('returncode') != 0:
        product = {'status': 'failed', 'result': 'backend command failed'}
        if args.backend_action == 'switch':
            product = {
                'status': 'failed',
                'selected_backend': '',
                'available_backends': ['codex', 'dry_run', 'mock'],
                'result': f'unknown backend: {args.name}',
            }
        print(json.dumps(product, ensure_ascii=False, indent=2))
        return int(result.get('returncode') or 1)
    raw = str(result.get('stdout') or '{}').strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {}
    if args.backend_action == 'switch':
        product = {'status': 'ok', 'selected_backend': payload.get('backend'), 'result': 'backend switched'}
    elif args.backend_action == 'health':
        product = {'status': 'ok', 'result': 'backend health checked', 'backends': payload.get('backends', {})}
    else:
        product = {
            'status': 'ok',
            'selected_backend': payload.get('selected', ''),
            'available_backends': payload.get('backends', []),
        }
    print(json.dumps(product, ensure_ascii=False, indent=2))
    return 0


def config_command(args) -> int:
    if args.config_action == 'backend':
        result = backend_command(argparse.Namespace(backend_action='switch', name=args.name, workspace=args.workspace))
        return result
    print_json({'status': 'failed', 'result': 'unknown config command'})
    return 2


def session_command(args) -> int:
    project = project_root(args.workspace)
    if not getattr(args, 'dogfood', False):
        print_json({'task': 'session', 'mode': 'blocked', 'result': 'unknown session command'})
        return 2
    result = delegate_capture('session_dogfood_runner.py', ['--workspace', str(project)])
    if getattr(args, 'debug', False):
        print(str(result.get('stdout') or '').strip())
        return int(result.get('returncode') or 0)
    payload = parse_json_output(result)
    readiness = ((payload.get('readiness') or {}).get('readiness')) or 'NOT_READY'
    print_json(
        {
            'task': 'session dogfood',
            'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
            'result': f'Report: .zoo-agent/session_dogfood/session_product_report.md; readiness: {readiness}',
        }
    )
    return int(result.get('returncode') or 0)


def workers_command(args) -> int:
    project = project_root(args.workspace)
    if getattr(args, 'real_dogfood', False):
        result = delegate_capture('real_worker_dogfood_runner.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        readiness = ((payload.get('readiness') or {}).get('readiness')) or 'NOT_READY'
        print_json(
            {
                'task': 'real worker dogfood',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': f'Report: .zoo-agent/real_worker_dogfood/project_operator_value_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'dogfood', False):
        result = delegate_capture('worker_router_dogfood_runner.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        readiness = ((payload.get('readiness') or {}).get('readiness')) or 'NOT_READY'
        print_json(
            {
                'task': 'workers dogfood',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': f'Report: .zoo-agent/worker_dogfood/worker_router_product_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'doctor', False):
        result = delegate_capture('worker_doctor.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print(str(result.get('stdout') or '').strip())
        return int(result.get('returncode') or 0)
    if getattr(args, 'list', False):
        result = delegate_capture('worker_registry.py', ['--workspace', str(project), '--list'])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        workers = [item for item in payload.get('workers') or [] if item.get('available')]
        labels = (
            ', '.join(str(item.get('worker_type') or item.get('name') or 'worker') for item in workers)
            or 'none available'
        )
        print_json({'task': 'workers list', 'mode': 'ready', 'result': f'Available worker roles: {labels}'})
        return int(result.get('returncode') or 0)
    if getattr(args, 'route_demo', False):
        result = delegate_capture('worker_router.py', ['--workspace', str(project), '--route-demo'])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        print_json(
            {
                'task': 'workers route demo',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': f'Selected: {payload.get("worker_role") or "Worker"}; routing: .zoo-agent/workers/routing_decision.json',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'workers', 'mode': 'blocked', 'result': 'unknown workers command'})
    return 2


def learning_command(args) -> int:
    project = project_root(args.workspace)
    common = ['--workspace', str(project)]
    if getattr(args, 'import_artifacts', False):
        command = [*common]
        if getattr(args, 'source', ''):
            command.extend(['--source', str(project_root(args.source))])
        result = delegate_capture('learning_artifact_importer.py', command)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'local learning import',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': 'Import report: .zoo-agent/learning/cross_project/import_report.json',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'build', False):
        steps = [
            ('learning_artifact_importer.py', common),
            ('next_action_pattern_miner.py', common),
            ('release_readiness_template_builder.py', common),
            ('worker_performance_memory.py', common),
            ('failure_taxonomy_builder.py', common),
            ('cross_project_insight_engine.py', common),
            ('learning_feedback_applier.py', common),
            ('cross_project_learning_report_generator.py', common),
        ]
        final_payload = {}
        for script, command in steps:
            result = delegate_capture(script, command)
            if getattr(args, 'debug', False):
                print(str(result.get('stdout') or '').strip())
            if result.get('returncode') != 0:
                print_json({'task': 'local learning build', 'mode': 'blocked', 'result': f'{script} failed'})
                return int(result.get('returncode') or 1)
            if script == 'cross_project_learning_report_generator.py':
                final_payload = parse_json_output(result)
        status_value = str(final_payload.get('status') or 'PARTIALLY_READY')
        print_json(
            {
                'task': 'local learning build',
                'mode': 'ready' if status_value == 'CROSS_PROJECT_LEARNING_097_READY' else 'partial',
                'result': f'Report: .zoo-agent/learning/cross_project/cross_project_learning_report.md; status: {status_value}',
            }
        )
        return 0
    if getattr(args, 'report', False):
        result = delegate_capture('cross_project_learning_report_generator.py', common)
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'local learning report',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': f'Report: .zoo-agent/learning/cross_project/cross_project_learning_report.md; status: {payload.get("status") or "unknown"}',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'doctor', False):
        init = delegate_capture('cross_project_store.py', common)
        report = delegate_capture('cross_project_learning_report_generator.py', common)
        payload = parse_json_output(report)
        if getattr(args, 'debug', False):
            print(str(init.get('stdout') or '').strip())
            print(str(report.get('stdout') or '').strip())
            return int(report.get('returncode') or init.get('returncode') or 0)
        print_json(
            {
                'task': 'local learning doctor',
                'mode': 'ready' if report.get('returncode') == 0 else 'blocked',
                'result': f'Store: .zoo-agent/learning/cross_project; status: {payload.get("status") or "unknown"}',
            }
        )
        return int(report.get('returncode') or init.get('returncode') or 0)
    if getattr(args, 'dogfood', False):
        result = delegate_capture('cross_project_learning_dogfood_runner.py', common)
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        readiness = str(payload.get('readiness_value') or 'NOT_READY')
        print_json(
            {
                'task': 'local learning dogfood',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': f'Report: .zoo-agent/learning_dogfood/learning_product_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'local learning', 'mode': 'blocked', 'result': 'unknown learning command'})
    return 2


def rollback(args) -> int:
    command = ['--workspace', workspace_arg(args.workspace), '--run-id', args.run_id, '--task-id', args.task_id]
    if args.dry_run or not args.yes:
        command.append('--dry-run')
    if args.yes:
        command.append('--yes')
    if args.confirm_current_branch:
        command.append('--confirm-current-branch')
    result = delegate_capture('rollback_task.py', command)
    if getattr(args, 'debug', False):
        print(str(result.get('stdout') or '').strip())
        return int(result.get('returncode') or 0)
    payload = parse_json_output(result)
    status = str(payload.get('status') or ('ok' if result.get('returncode') == 0 else 'error'))
    progress = 'dry_run' if status == 'dry_run' else status
    print_json(
        {
            'goal': 'rollback plan',
            'progress': progress,
            'result': 'rollback ready' if result.get('returncode') == 0 else 'rollback error',
        }
    )
    return int(result.get('returncode') or 0)


def reroute(args) -> int:
    command = [
        '--workspace',
        workspace_arg(args.workspace),
        '--run-id',
        args.run_id,
        '--task-id',
        args.task_id,
        '--path',
        args.path,
        '--timeout-seconds',
        str(args.timeout_seconds),
    ]
    for flag, value in [
        ('--new-run-id', args.new_run_id),
        ('--new-task-id', args.new_task_id),
        ('--input-text', args.input_text),
        ('--goal-id', args.goal_id),
        ('--codex-home', args.codex_home),
        ('--profile', args.profile),
    ]:
        if value:
            command.extend([flag, value])
    if args.dry_run:
        command.append('--dry-run')
    if args.worker_dry_run:
        command.append('--worker-dry-run')
    if args.no_execute_governed_workers:
        command.append('--no-execute-governed-workers')
    if args.discard_failed_worktree:
        command.append('--discard-failed-worktree')
    return delegate('reroute_task.py', command)


def map_command(args) -> int:
    command = ['--workspace', workspace_arg(args.workspace)]
    if args.map_action == 'refresh':
        command.append('--refresh')
    elif args.map_action == 'promote':
        command.append('--promote')
    if args.promote_if_missing:
        command.append('--promote-if-missing')
    if args.dry_run:
        command.append('--dry-run')
    return delegate('check_project_map_alignment.py', command)


def standards(args) -> int:
    command = ['--workspace', workspace_arg(args.workspace)]
    if args.standards_action == 'check':
        command.append('--check')
    elif args.standards_action == 'promote':
        command.append('--promote')
    if args.refresh:
        command.append('--refresh')
    if args.dry_run:
        command.append('--dry-run')
    return delegate('init_project_instructions.py', command)


def stats_command(args) -> int:
    """Show usage statistics and cost summary."""
    from cost_dashboard import get_usage_summary, record_call

    project = project_root(args.workspace)
    if getattr(args, 'record', False):
        result = record_call(project, args.record_worker or 'unknown', args.record_duration or 0.0)
        print_json({'status': 'recorded', **result})
        return 0
    summary = get_usage_summary(project)
    print_json({'task': 'usage stats', 'mode': 'ready', 'result': summary})
    return 0


def audit_command(args) -> int:
    """Query the audit log."""
    from audit_log import daily_summary, log_event, query_log

    project = project_root(args.workspace)
    if getattr(args, 'summary', False):
        result = daily_summary(project)
        print_json({'task': 'audit summary', 'mode': 'ready', 'result': result})
        return 0
    if getattr(args, 'log', False):
        event_type = args.log_event or 'manual'
        entry = log_event(project, event_type=event_type, worker=args.log_worker or '', task=args.log_task or '')
        print_json({'task': 'audit log', 'mode': 'logged', 'result': entry})
        return 0
    entries = query_log(
        project,
        limit=getattr(args, 'limit', 50),
        event_type=getattr(args, 'event_type', ''),
        worker=getattr(args, 'worker', ''),
    )
    print_json({'task': 'audit query', 'mode': 'ready', 'result': {'entries': entries, 'count': len(entries)}})
    return 0
