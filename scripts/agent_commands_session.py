#!/usr/bin/env python3
"""Session runtime and pipeline command handlers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from agent_utils import (
    delegate,
    delegate_capture,
    ensure_bootstrap_before_run,
    prepare_bootstrap_workspace,
    print_bootstrap_output,
    print_json,
    run_command,
    run_command_capture,
    workspace_arg,
    write_onboarding_artifacts,
)
from backend_registry import read_backend_selection
from check_project_readiness import analyze_project_readiness
from runtime_common import initialize_loop, load_json, project_root, set_active_goal, utc_now, write_json
from update_runtime_metrics import update_metrics


def bootstrap(args) -> int:
    project = project_root(args.workspace)
    marker_path = project / '.zoo-agent' / 'runtime-v4.json'
    lock_path = project / '.zoo-agent' / 'bootstrap.lock'
    prepare_code, prepare_report = prepare_bootstrap_workspace(project, args)
    if prepare_code != 0:
        print_bootstrap_output(
            {'status': prepare_report.get('status'), 'workspace': str(project), **prepare_report},
            debug=getattr(args, 'debug', False),
        )
        return prepare_code
    if args.dry_run:
        print_bootstrap_output(
            {
                'status': 'dry_run',
                'workspace': str(project),
                'version': '',
                'workspace_preparation': prepare_report,
                'would_create_or_update': [
                    str(marker_path),
                    str(lock_path),
                    str(project / '.zoo-agent' / 'project-profile.json'),
                    str(project / '.zoo-agent' / 'project-readiness.json'),
                    str(project / '.zoo-agent' / 'bootstrap-report.md'),
                    str(project / 'AGENTS.md'),
                ],
            },
            debug=getattr(args, 'debug', False),
        )
        return 0
    initial_readiness = analyze_project_readiness(project)
    missing_artifacts = [
        str(path)
        for path in [
            project / 'AGENTS.md',
            project / '.zoo-agent' / 'code-standards.json',
            project / '.zoo-agent' / 'project-map.json',
            project / '.zoo-agent' / 'project-map.md',
            project / '.zoo-agent' / 'project-profile.json',
            project / '.zoo-agent' / 'project-readiness.json',
            project / '.zoo-agent' / 'bootstrap-report.md',
        ]
        if not path.exists()
    ]
    if (
        lock_path.exists()
        and not args.force
        and not args.refresh_instructions
        and not args.dry_run
        and not missing_artifacts
    ):
        report = {
            'status': 'already_bootstrapped',
            'workspace': str(project),
            'runtime_marker': str(marker_path),
            'lock': str(lock_path),
            'already_bootstrapped': True,
            'missing_artifacts': missing_artifacts,
            'message': 'already bootstrapped; bootstrap.lock exists and no project files were overwritten.',
        }
        print_bootstrap_output(report, debug=getattr(args, 'debug', False))
        return 0
    already_bootstrapped = marker_path.exists() and not args.force
    if already_bootstrapped:
        marker = load_json(marker_path)
        goal = {'goal_id': marker.get('goal_id', ''), '_path': ''}
    else:
        goal = set_active_goal(
            project,
            args.goal or 'Operate this project through the CLI-first AI Agent Runtime with bounded Codex execution.',
            goal_id=args.goal_id,
            success_criteria=args.success_criteria,
            constraints=args.constraint,
            activate=True,
            source='agent.py bootstrap',
        )
        loop_state = initialize_loop(project, max_iteration=args.max_iteration, source='agent.py bootstrap')
        update_metrics(project, path='fast', status='bootstrap_initialized')
        marker = {
            'schema_version': '4.0',
            'generated_by': 'agent.py bootstrap',
            'generated_at': utc_now(),
            'workspace': str(project),
            'entrypoints': {
                'bootstrap': 'agent bootstrap',
                'run': 'agent run <input>',
                'fast': 'agent run --fast <input>',
                'parallel': 'agent run --parallel <input>',
                'governed': 'agent run --governed <input>',
            },
            'runtime_model': {
                'cli_runtime': 'task routing, goal, loop, execution control',
                'codex_cli': 'execution backend',
                'gpt': 'decision layer',
                'deepseek': 'cheap worker',
                'zoo_code': 'optional UI layer',
            },
            'goal_id': goal.get('goal_id'),
            'loop_state': loop_state,
        }
        write_json(marker_path, marker)
    legacy_result = None
    if args.with_project_bootstrap:
        command = [
            sys.executable,
            str(ROOT / 'scripts' / 'agent_bootstrap.py'),
            '--project',
            str(project),
            '--mode',
            args.mode,
        ]
        if args.goal:
            command.extend(['--goal', args.goal])
        if args.codex_home:
            command.extend(['--codex-home', args.codex_home])
        if args.dry_run:
            command.append('--dry-run')
        legacy_result = run_command(command, ROOT)
    instruction_args = ['--workspace', str(project)]
    if args.refresh_instructions:
        instruction_args.append('--refresh')
    if args.dry_run:
        instruction_args.append('--dry-run')
    instruction_capture = delegate_capture('init_project_instructions.py', instruction_args)
    instruction_result = int(instruction_capture.get('returncode') or 0)
    map_args = ['--workspace', str(project), '--refresh', '--promote-if-missing']
    if args.dry_run:
        map_args.append('--dry-run')
    map_capture = delegate_capture('check_project_map_alignment.py', map_args)
    map_result = int(map_capture.get('returncode') or 0)
    onboarding = write_onboarding_artifacts(
        project,
        args,
        initialized_git=bool(prepare_report.get('initialized_git')),
        already_bootstrapped=already_bootstrapped,
        base_readiness=initial_readiness,
    )
    report = {
        'status': 'ready'
        if legacy_result in {None, 0} and instruction_result == 0 and map_result in {0, 10}
        else 'ready_with_bootstrap_warnings',
        'version': '',
        'workspace': str(project),
        'runtime_marker': str(marker_path),
        'lock': str(lock_path),
        'already_bootstrapped': already_bootstrapped,
        'workspace_preparation': prepare_report,
        'goal_id': goal.get('goal_id'),
        'goal_path': goal.get('_path', ''),
        'loop_state_path': str(project / '.zoo-agent' / 'loop_state.json'),
        'with_project_bootstrap': args.with_project_bootstrap,
        'project_bootstrap_returncode': legacy_result,
        'instruction_init_returncode': instruction_result,
        'project_map_returncode': map_result,
        'safe_for_level_0_1_trial': onboarding.get('project_readiness', {}).get('safe_for_level_0_1_trial', False),
        'blocking_issues': onboarding.get('project_readiness', {}).get('blocking_issues', []),
        'warnings': onboarding.get('project_readiness', {}).get('warnings', []),
        'next_actions': onboarding.get('project_readiness', {}).get('next_actions', []),
        'onboarding_actions': onboarding.get('actions', []),
    }
    if getattr(args, 'debug', False):
        report['instruction_init_stdout'] = instruction_capture.get('stdout', '')
        report['instruction_init_stderr'] = instruction_capture.get('stderr', '')
        report['project_map_stdout'] = map_capture.get('stdout', '')
        report['project_map_stderr'] = map_capture.get('stderr', '')
    if not args.dry_run and report['status'] == 'ready':
        write_json(
            lock_path,
            {
                'schema_version': '4.0',
                'generated_by': 'agent.py bootstrap',
                'generated_at': utc_now(),
                'workspace': str(project),
                'runtime_marker': str(marker_path),
                'goal_id': goal.get('goal_id'),
            },
        )
    print_bootstrap_output(report, debug=getattr(args, 'debug', False))
    return 0 if report['status'] == 'ready' else 10


def legacy_run(args) -> int:
    ensure_bootstrap_before_run(args)
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'route_task.py'),
        '--workspace',
        workspace_arg(args.workspace),
        '--legacy-runtime',
    ]
    if args.run_id:
        command.extend(['--run-id', args.run_id])
    if args.task_id:
        command.extend(['--task-id', args.task_id])
    if args.goal_id:
        command.extend(['--goal-id', args.goal_id])
    if args.fast:
        command.append('--fast')
    if args.parallel:
        command.append('--parallel')
    if args.governed:
        command.append('--governed')
    if args.dry_run:
        command.append('--dry-run')
    if args.worker_dry_run:
        command.append('--worker-dry-run')
    if args.allow_ambiguous_fast:
        command.append('--allow-ambiguous-fast')
    if args.no_execute_governed_workers:
        command.append('--no-execute-governed-workers')
    if args.discard_failed_worktree:
        command.append('--discard-failed-worktree')
    if args.ephemeral:
        command.append('--ephemeral')
    if args.skip_health_check:
        command.append('--skip-health-check')
    for flag, value in [
        ('--changed-file-estimate', args.changed_file_estimate),
        ('--max-workers', args.max_workers),
        ('--timeout-seconds', args.timeout_seconds),
        ('--no-output-timeout-seconds', args.no_output_timeout_seconds),
        ('--test-timeout-seconds', args.test_timeout_seconds),
        ('--max-retries', args.max_retries),
        ('--max-iteration', args.max_iteration),
    ]:
        command.extend([flag, str(value)])
    for flag, value in [
        ('--sandbox', args.sandbox),
        ('--profile', args.profile),
        ('--codex-home', args.codex_home),
        ('--start-point', args.start_point),
    ]:
        if value:
            command.extend([flag, value])
    for item in args.allowed_file:
        command.extend(['--allowed-file', item])
    for item in args.denied_file:
        command.extend(['--denied-file', item])
    for item in args.test_command:
        command.extend(['--test-command', item])
    command.extend(['--input-text', ' '.join(args.input).strip()])
    return run_command(command, ROOT)


def run(args) -> int:
    force_path = ''
    if getattr(args, 'fast', False):
        force_path = 'fast'
    elif getattr(args, 'parallel', False):
        force_path = 'parallel'
    elif getattr(args, 'governed', False):
        force_path = 'governed'
    if getattr(args, 'legacy_runtime', False):
        return legacy_run(args)
    return pipeline(
        argparse.Namespace(
            workspace=args.workspace,
            run_id=args.run_id,
            task_id=args.task_id,
            goal_id=args.goal_id,
            allowed_file=args.allowed_file,
            denied_file=args.denied_file,
            force_path=force_path,
            max_iterations=args.max_iteration,
            dry_run=args.dry_run,
            allow_actual=not args.dry_run and not args.worker_dry_run,
            sandbox=args.sandbox,
            codex_home=args.codex_home,
            backend=args.backend,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            debug=getattr(args, 'debug', False),
            input=args.input,
        )
    )


def pipeline(args) -> int:
    ensure_bootstrap_before_run(args)
    project = project_root(args.workspace)
    selected_backend = str(getattr(args, 'backend', '') or read_backend_selection(project))
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'pipeline_loop.py'),
        '--workspace',
        str(project),
        '--max-iterations',
        str(args.max_iterations),
        '--sandbox',
        args.sandbox,
        '--timeout-seconds',
        str(args.timeout_seconds),
        '--max-retries',
        str(getattr(args, 'max_retries', 0)),
        '--backend',
        selected_backend,
    ]
    if args.run_id:
        command.extend(['--run-id', args.run_id])
    if getattr(args, 'task_id', ''):
        command.extend(['--task-id', args.task_id])
    if args.goal_id:
        command.extend(['--goal-id', args.goal_id])
    if args.force_path:
        command.extend(['--force-path', args.force_path])
    if args.dry_run:
        command.append('--dry-run')
    if args.allow_actual:
        command.append('--allow-actual')
    if args.codex_home:
        command.extend(['--backend-option', f'codex_home={args.codex_home}'])
    for item in args.allowed_file:
        command.extend(['--allowed-file', item])
    for item in args.denied_file:
        command.extend(['--denied-file', item])
    command.extend(args.input)
    proc = run_command_capture(command, ROOT)
    payload: dict = {}
    stdout = str(proc.get('stdout') or '').strip()
    if stdout.startswith('{'):
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {}
    if getattr(args, 'debug', False):
        if stdout:
            print(stdout)
        else:
            print_json({'returncode': proc.get('returncode'), 'stderr': proc.get('stderr', '')})
        return int(proc.get('returncode') or 0)
    if proc.get('returncode') != 0:
        print_json({'goal': ' '.join(args.input).strip(), 'progress': 'blocked', 'result': 'error'})
        return int(proc.get('returncode') or 1)
    product = {
        'goal': ' '.join(args.input).strip(),
        'progress': 'complete' if payload.get('converged') else 'in_progress',
        'result': payload.get('final_verdict') or 'unknown',
    }
    print_json(product)
    return 0


def plan_big(args) -> int:
    run_id = args.run_id or 'run-big-task'
    text = ' '.join(args.input).strip()
    command = ['--workspace', workspace_arg(args.workspace), '--run-id', run_id, '--input-text', text]
    if args.goal_id:
        command.extend(['--goal-id', args.goal_id])
    result = delegate('generate_big_task_contract.py', command)
    delegate('render_big_task_plan.py', ['--workspace', workspace_arg(args.workspace), '--run-id', run_id])
    return result


def decompose_big(args) -> int:
    run_id = args.run_id or 'run-big-task'
    text = ' '.join(args.input).strip()
    if text:
        command = ['--workspace', workspace_arg(args.workspace), '--run-id', run_id, '--input-text', text]
        if args.goal_id:
            command.extend(['--goal-id', args.goal_id])
        result = delegate('generate_big_task_contract.py', command)
        if result not in {0, 10}:
            return result
    command = ['--workspace', workspace_arg(args.workspace), '--run-id', run_id]
    if args.allow_leaf_actual:
        command.append('--allow-leaf-actual')
    result = delegate('decompose_big_task_to_leaf_contracts.py', command)
    if result != 0:
        return result
    delegate('check_leaf_task_contracts.py', ['--workspace', workspace_arg(args.workspace), '--run-id', run_id])
    delegate('schedule_leaf_execution.py', ['--workspace', workspace_arg(args.workspace), '--run-id', run_id])
    return result


def aggregate_big(args) -> int:
    command = [
        '--workspace',
        workspace_arg(args.workspace),
        '--run-id',
        args.run_id,
        '--max-iterations',
        str(args.max_iterations),
    ]
    if args.goal_id:
        command.extend(['--goal-id', args.goal_id])
    return delegate('run_parent_aggregation_gate.py', command)


def goal_loop(args) -> int:
    command = [
        '--workspace',
        workspace_arg(args.workspace),
        '--run-id',
        args.run_id,
        '--max-iterations',
        str(args.max_iterations),
    ]
    if args.goal_id:
        command.extend(['--goal-id', args.goal_id])
    if args.no_advance:
        command.append('--no-advance')
    if args.no_next_goal_suggestions:
        command.append('--no-next-goal-suggestions')
    return delegate('goal_loop_engine.py', command)


def global_loop(args) -> int:
    command = [
        '--workspace',
        workspace_arg(args.workspace),
        '--max-iterations',
        str(args.max_iterations),
        '--max-continuous-goal-iterations',
        str(args.max_continuous_goal_iterations),
    ]
    if args.backend_health:
        command.extend(['--backend-health', args.backend_health])
    if args.no_advance:
        command.append('--no-advance')
    return delegate('global_loop_engine.py', command)


def integration_check(args) -> int:
    command = ['--workspace', workspace_arg(args.workspace), '--run-id', args.run_id]
    if args.yes:
        command.append('--yes')
    else:
        command.append('--dry-run')
    return delegate('create_integration_worktree.py', command)
