#!/usr/bin/env python3
"""Command handler functions for the agent CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from agent_utils import (
    clean_progress,
    delegate,
    delegate_capture,
    ensure_bootstrap_before_run,
    latest_run_id,
    parse_json_output,
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
