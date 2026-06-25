#!/usr/bin/env python3
"""Goal, loop, and review command handlers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from agent_utils import (
    clean_progress,
    delegate,
    delegate_capture,
    latest_run_id,
    parse_json_output,
    print_json,
    workspace_arg,
)
from runtime_common import project_root


def review(args) -> int:
    project = project_root(args.workspace)
    run_id = args.run_id or latest_run_id(project)
    if not run_id:
        print('No run_id supplied and no local run was found.', file=sys.stderr)
        return 2
    command = ['--workspace', str(project), '--run-id', run_id]
    for enabled, flag in [
        (args.governance_only, '--governance-only'),
        (args.allow_missing_tests, '--allow-missing-tests'),
        (args.allow_open_risks, '--allow-open-risks'),
        (args.allow_task_board_warnings, '--allow-task-board-warnings'),
        (args.allow_project_readiness_blocks, '--allow-project-readiness-blocks'),
        (args.allow_architecture_blocks, '--allow-architecture-blocks'),
        (args.accept_parent_aggregation, '--accept-parent-aggregation'),
    ]:
        if enabled:
            command.append(flag)
    return delegate('runtime_review.py', command)


def goal_command(args) -> int:
    if args.goal_action == 'set':
        if not str(args.goal or '').strip():
            print_json({'goal': '', 'progress': 'blocked', 'result': 'missing goal'})
            return 2
        command = ['--workspace', workspace_arg(args.workspace), '--goal', args.goal]
        if args.goal_id:
            command.extend(['--goal-id', args.goal_id])
        command.extend(['--priority', str(args.priority)])
        for item in args.resource:
            command.extend(['--resource', item])
        for item in args.depends_on:
            command.extend(['--depends-on', item])
        for item in args.success_criteria:
            command.extend(['--success-criteria', item])
        for item in args.constraint:
            command.extend(['--constraint', item])
        for item in args.non_goal:
            command.extend(['--non-goal', item])
        command.extend(['--risk-tolerance', args.risk_tolerance])
        if args.no_activate:
            command.append('--no-activate')
        result = delegate_capture('set_goal.py', command)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        goal_payload = payload.get('goal') if isinstance(payload.get('goal'), dict) else {}
        print_json(
            {
                'goal': goal_payload.get('goal') or args.goal,
                'progress': 'active' if payload.get('active') is not False else 'paused',
                'result': 'goal set' if result.get('returncode') == 0 else 'error',
            }
        )
        return int(result.get('returncode') or 0)
    if args.goal_action == 'clear':
        result = delegate_capture('set_goal.py', ['--workspace', workspace_arg(args.workspace), '--clear'])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
        else:
            print_json({'goal': 'none', 'progress': 'cleared', 'result': 'goal cleared'})
        return int(result.get('returncode') or 0)
    if args.goal_action == 'list':
        result = delegate_capture('goal_state_manager.py', ['list', '--workspace', workspace_arg(args.workspace)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        goals = payload.get('goals') if isinstance(payload.get('goals'), list) else []
        active = next((item for item in goals if item.get('status') == 'active'), {}) if goals else {}
        print_json(
            {
                'goal': active.get('goal') or f'{len(goals)} goals',
                'progress': clean_progress(active.get('progress', 0) if active else 0),
                'result': f'{len(goals)} goals',
            }
        )
        return int(result.get('returncode') or 0)
    if args.goal_action in {'pause', 'resume', 'complete', 'backlog', 'block'}:
        if not args.goal_id:
            print(f'goal {args.goal_action} requires --goal-id.', file=sys.stderr)
            return 2
        result = delegate_capture(
            'goal_state_manager.py',
            [args.goal_action, '--workspace', workspace_arg(args.workspace), '--goal-id', args.goal_id],
        )
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
        else:
            print_json({'goal': args.goal_id, 'progress': args.goal_action, 'result': f'goal {args.goal_action}'})
        return int(result.get('returncode') or 0)
    if args.goal_action == 'schedule':
        command = [
            '--workspace',
            workspace_arg(args.workspace),
            '--max-continuous-iterations',
            str(args.max_continuous_iterations),
        ]
        if args.backend_health:
            command.extend(['--backend-health', args.backend_health])
        if args.multi_goal_mode:
            command.append('--multi-goal-mode')
        return delegate('goal_scheduler.py', command)
    if args.goal_action == 'conflicts':
        command = ['--workspace', workspace_arg(args.workspace)]
        if args.apply:
            command.append('--apply')
        return delegate('goal_conflict_detector.py', command)
    command = ['--workspace', workspace_arg(args.workspace)]
    if args.goal_id:
        command.extend(['--goal-id', args.goal_id])
    if args.goal_action in {'status', 'show'}:
        result = delegate_capture('get_goal.py', command)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        goal_payload = payload.get('goal') if isinstance(payload.get('goal'), dict) else {}
        print_json(
            {
                'goal': goal_payload.get('goal') or 'no active goal',
                'progress': 'active' if payload.get('active') else 'inactive',
                'result': payload.get('status') or 'unknown',
            }
        )
        return int(result.get('returncode') or 0)
    print(f'Unsupported goal action: {args.goal_action}', file=sys.stderr)
    return 2


def loop_command(args) -> int:
    command = ['--workspace', workspace_arg(args.workspace)]
    if args.run_id:
        command.extend(['--run-id', args.run_id])
    if hasattr(args, 'max_iterations'):
        command.extend(['--max-iterations', str(args.max_iterations)])
    if args.loop_action == 'reset':
        command.append('--reset')
    elif args.loop_action == 'stop':
        command.append('--stop')
    elif args.loop_action == 'set':
        command.append('--set-max')
    elif args.loop_action == 'explain':
        return delegate('check_loop_convergence.py', ['--workspace', workspace_arg(args.workspace)])
    elif args.loop_action == 'status':
        pass
    else:
        print(f'Unsupported loop action: {args.loop_action}', file=sys.stderr)
        return 2
    return delegate('loop_controller.py', command)


def codex_health(args) -> int:
    command = [
        '--workspace',
        workspace_arg(args.workspace),
        '--mode',
        args.mode,
        '--timeout-seconds',
        str(args.timeout_seconds),
        '--no-output-timeout-seconds',
        str(args.no_output_timeout_seconds),
    ]
    if args.codex_home:
        command.extend(['--codex-home', args.codex_home])
    if args.skip_real_codex:
        command.append('--skip-real-codex')
    return delegate('check_codex_backend_health.py', command)
