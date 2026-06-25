#!/usr/bin/env python3
"""Command handler functions for the agent CLI entry point."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from agent_utils import (
    active_job_blocks_unified_prompt,
    actual_execution_issue,
    clean_progress,
    delegate,
    delegate_capture,
    is_bootstrapped,
    latest_run_id,
    make_run_namespace,
    migrate_legacy_seed_preview_queue,
    one_off_report,
    parse_json_output,
    pipeline_failure_summary,
    prepare_bootstrap_workspace,
    print_bootstrap_output,
    print_json,
    public_report_with_overview,
    record_seed_queue_job,
    record_unified_job,
    run_command,
    run_command_capture,
    run_direct_docs_prompt,
    run_preview_artifact_prompt,
    run_seed_queue_prompt,
    safe_print_text,
    user_task_result,
    workspace_arg,
    write_onboarding_artifacts,
)
from backend_registry import read_backend_selection
from bounded_docs_writer import apply_docs_patch
from check_project_readiness import analyze_project_readiness
from job_controller import continue_job, show_job_inbox, start_or_update_job, stop_job
from job_state_store import (
    load_current_job,
)
from preview_artifact_writer import write_preview_artifact
from prompt_intent_router import classify_prompt
from runtime_common import initialize_loop, load_json, project_root, set_active_goal, utc_now, write_json
from seed_action_queue import load_queue as load_seed_queue
from seed_action_queue import next_pending_action as next_seed_action
from seed_action_queue import run_batch as run_seed_batch
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


def ensure_bootstrap_before_run(args) -> None:
    project = project_root(args.workspace)
    if is_bootstrapped(project):
        return
    return


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


def start_command(args) -> int:
    project = project_root(args.workspace)
    goal = ' '.join(args.goal).strip()
    if not goal:
        print_json(user_task_result(task='', mode='blocked', result='please describe the project goal'))
        return 2
    if getattr(args, 'debug', False):
        result = delegate_capture(
            'session_runtime_engine.py', ['--workspace', str(project), '--mode', args.mode, '--start', goal]
        )
        print(str(result.get('stdout') or '').strip())
        return int(result.get('returncode') or 0)
    payload = start_or_update_job(
        project, goal, mode=args.mode, max_steps=args.max_steps, backend=args.backend, steps=getattr(args, 'steps', 0)
    )
    print(str(payload.get('message') or '').strip())
    print('\nTip: next time you can just run:')
    print(f'agent "{goal}"')
    return 0 if payload.get('status') != 'blocked' else 2


def stop_command(args) -> int:
    project = project_root(args.workspace)
    if getattr(args, 'debug', False):
        result = delegate_capture('session_runtime_engine.py', ['--workspace', str(project), '--stop'])
        print(str(result.get('stdout') or '').strip())
        return int(result.get('returncode') or 0)
    payload = stop_job(project)
    print(str(payload.get('message') or '').strip())
    return 0


def continue_command(args) -> int:
    project = project_root(args.workspace)
    migrate_legacy_seed_preview_queue(project)
    queue = load_seed_queue(project)
    if queue.get('actions') and next_seed_action(project):
        job = load_current_job(project)
        goal = str((job or {}).get('goal') or queue.get('goal') or '')
        result = run_seed_batch(project, goal=goal, max_steps=3)
        record_seed_queue_job(project, goal=goal, queue_result=result)
        changed = [str(item) for item in result.get('changed_files') or []]
        pending = next_seed_action(project)
        status = 'Needs attention' if result.get('status') == 'needs_attention' else 'Done'
        next_text = 'agent continue' if pending else 'agent "<next project goal>"'
        actions = [
            str(item.get('title') or item.get('action_id') or '')
            for item in result.get('actions') or []
            if isinstance(item, dict)
        ]
        why = 'Continued the seed prompt project through a safe reviewable batch.'
        if actions:
            why = f'Completed batch: {", ".join(actions)}.'
        print(
            public_report_with_overview(
                project,
                status=status,
                goal=goal,
                changed_files=changed,
                why=why,
                next_action=next_text,
                attention='; '.join(
                    str(item.get('reason') or item) for item in result.get('blocked') or [] if isinstance(item, dict)
                )
                if result.get('status') == 'needs_attention'
                else '',
                stop_reason=str(result.get('stop_reason') or 'reviewable_batch_complete'),
            )
        )
        return 0
    if queue.get('actions') and not next_seed_action(project):
        job = load_current_job(project)
        goal = str((job or {}).get('goal') or queue.get('goal') or '')
        print(
            public_report_with_overview(
                project,
                status='Done',
                goal=goal,
                changed_files=[],
                why='All safe starter actions from the seed prompt are complete.',
                next_action='Give the next prompt when you want to keep developing the project.',
                stop_reason='queue_completed',
            )
        )
        return 0
    steps = getattr(args, 'steps', 0) or args.max_steps or 1
    payload = continue_job(project, mode=args.mode, steps=steps, backend=args.backend)
    print(str(payload.get('message') or '').strip())
    return 0


def status(args) -> int:
    project = project_root(args.workspace)
    if not getattr(args, 'debug', False) and not getattr(args, 'no_write', False):
        payload = show_job_inbox(project)
        print(str(payload.get('message') or '').strip())
        print('\nTip: `agent` also shows this inbox.')
        return 0
    session_result = delegate_capture('session_runtime_engine.py', ['--workspace', str(project), '--status'])
    session_payload = parse_json_output(session_result)
    if session_payload and not getattr(args, 'debug', False):
        print_json(
            {
                'task': session_payload.get('task') or 'session',
                'mode': 'status',
                'result': session_payload.get('result')
                or 'Session: status: unknown; digest: .zoo-agent/session/session_digest.md; cockpit: .zoo-agent/cockpit/index.html',
            }
        )
        return int(session_result.get('returncode') or 0)
    session = load_json(project / '.zoo-agent' / 'autopilot' / 'session.json')
    progress_payload = load_json(project / '.zoo-agent' / 'autopilot' / 'progress.json')
    cockpit_path = project / '.zoo-agent' / 'cockpit' / 'index.html'
    cockpit_hint = (
        ' Project Cockpit: .zoo-agent/cockpit/index.html'
        if cockpit_path.exists()
        else ' Run `agent cockpit` to generate a local Project Cockpit.'
    )
    if session and not getattr(args, 'debug', False):
        task = str(session.get('goal') or 'project')
        result_text = str(session.get('status') or progress_payload.get('status') or 'doing')
        result_text = f'{result_text};{cockpit_hint}'
        print_json({'task': task, 'mode': 'status', 'result': result_text})
        return 0
    command = ['--workspace', workspace_arg(args.workspace)]
    if args.run_id:
        command.extend(['--run-id', args.run_id])
    if args.no_write:
        command.append('--no-write')
    result = delegate_capture('runtime_status.py', command)
    payload = parse_json_output(result)
    if getattr(args, 'debug', False):
        safe_print_text(str(result.get('stdout') or '').strip())
        return int(result.get('returncode') or 0)
    goals = (
        ((payload.get('goal_state') or {}).get('goals') or []) if isinstance(payload.get('goal_state'), dict) else []
    )
    active = next((item for item in goals if item.get('status') == 'active'), {}) if isinstance(goals, list) else {}
    task_text = str(active.get('goal') or active.get('goal_id') or 'status')
    progress = clean_progress(active.get('progress', 0) if active else 0)
    summary = payload.get('status') or 'unknown'
    if active:
        summary = f'{summary}; progress {progress}'
    summary = f'{summary};{cockpit_hint}'
    print_json({'task': task_text, 'mode': 'status', 'result': summary})
    return int(result.get('returncode') or 0)


def cockpit_command(args) -> int:
    project = project_root(args.workspace)
    if getattr(args, 'dogfood', False):
        result = delegate_capture('cockpit_dogfood_runner.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        readiness = str(payload.get('readiness_value') or 'unknown')
        print_json(
            {
                'task': 'project cockpit dogfood',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': f'Report: .zoo-agent/cockpit_dogfood/cockpit_ux_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    result = delegate_capture('cockpit_renderer.py', ['--workspace', str(project)])
    if getattr(args, 'debug', False):
        print(str(result.get('stdout') or '').strip())
        return int(result.get('returncode') or 0)
    if result.get('returncode') != 0:
        print_json({'task': 'project cockpit', 'mode': 'blocked', 'result': 'could not generate Project Cockpit'})
        return int(result.get('returncode') or 1)
    print_json(
        {
            'task': 'project cockpit',
            'mode': 'ready',
            'result': 'Open: .zoo-agent/cockpit/index.html; Then: agent status, agent continue, agent stop, agent undo',
        }
    )
    return 0


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


def interactive_help() -> str:
    return '\n'.join(
        [
            'Try:',
            '  fix README typo',
            '  improve onboarding docs --preview',
            '  agent status',
            '  agent undo',
            '  /exit',
        ]
    )


def interactive_shell(workspace: str = '.') -> int:
    project = project_root(workspace)
    dry_run = os.environ.get('AGENT_INTERACTIVE_DRY_RUN') == '1'
    print(interactive_help())
    while True:
        try:
            line = input('agent> ').strip()
        except EOFError:
            print()
            return 0
        if not line:
            continue
        if line in {'/exit', 'exit', 'quit'}:
            return 0
        if line == '/help':
            print(interactive_help())
            continue
        try:
            parts = __import__('shlex').split(line)
        except ValueError as exc:
            print(f'Could not parse command: {exc}')
            continue
        if not parts:
            continue
        command = parts[0]
        try:
            if command == '/status':
                status(
                    argparse.Namespace(
                        workspace=str(project), run_id='', no_write='--no-write' in parts[1:], debug=False
                    )
                )
            elif command == '/review':
                review(argparse.Namespace(workspace=str(project), run_id=parts[1] if len(parts) > 1 else ''))
            elif command == '/reroute':
                if len(parts) < 4:
                    print('Usage: /reroute <run-id> <task-id> <fast|parallel|governed>')
                    continue
                reroute(
                    argparse.Namespace(
                        workspace=str(project),
                        run_id=parts[1],
                        task_id=parts[2],
                        path=parts[3],
                        timeout_seconds=360,
                        new_run_id='',
                        new_task_id='',
                        input_text='',
                        goal_id='',
                        codex_home='',
                        profile='',
                        dry_run=False,
                        worker_dry_run=False,
                        no_execute_governed_workers=False,
                        discard_failed_worktree=False,
                    )
                )
            elif command == '/rollback':
                if len(parts) < 3:
                    print('Usage: /rollback <run-id> <task-id> [--yes]')
                    continue
                rollback(
                    argparse.Namespace(
                        workspace=str(project),
                        run_id=parts[1],
                        task_id=parts[2],
                        dry_run='--yes' not in parts[3:],
                        yes='--yes' in parts[3:],
                        confirm_current_branch='--confirm-current-branch' in parts[3:],
                    )
                )
            elif command == '/goal':
                if len(parts) < 2:
                    goal_command(argparse.Namespace(goal_action='show', workspace=str(project), goal_id=''))
                else:
                    goal_command(
                        argparse.Namespace(
                            goal_action='set',
                            workspace=str(project),
                            goal=' '.join(parts[1:]),
                            goal_id='',
                            success_criteria=[],
                            constraint=[],
                            non_goal=[],
                            risk_tolerance='low',
                            priority=50,
                            resource=[],
                            depends_on=[],
                            no_activate=False,
                        )
                    )
            elif command == '/loop':
                action = parts[1] if len(parts) > 1 else 'status'
                loop_command(
                    argparse.Namespace(loop_action=action, workspace=str(project), run_id='', max_iterations=5)
                )
            elif command.startswith('/'):
                print('Unknown command. Use /help.')
            else:
                run(make_run_namespace(str(project), line, dry_run=dry_run))
        except subprocess.CalledProcessError as exc:
            print(f'Command failed with exit code {exc.returncode}')


def run_unified_prompt(args, text: str) -> int:
    project = project_root(args.workspace)
    intent = classify_prompt(project, text, allowed_files=getattr(args, 'allowed_file', []))
    intent_name = str(intent.get('intent') or '')
    blocking_job = active_job_blocks_unified_prompt(project, text)
    if blocking_job and intent_name in {'single_step_edit', 'seed_prompt_execution'}:
        print(
            public_report_with_overview(
                project,
                status='Needs attention',
                goal=text,
                changed_files=[],
                why='Another project job is currently active.',
                next_action='Run agent to inspect it, or agent stop before switching tasks.',
                attention=f'Current job: {blocking_job}',
                stop_reason='active_job_requires_review',
            )
        )
        return 2
    if intent_name == 'unsafe_or_needs_confirmation':
        reason = str(intent.get('reason') or 'high-risk operation')
        record_unified_job(project, goal=text, status='Needs attention', changed_files=[], attention_reason=reason)
        print(
            public_report_with_overview(
                project,
                status='Needs attention',
                goal=text,
                changed_files=[],
                why='The prompt asks for an operation that should not run automatically.',
                next_action='Revise the prompt to remove the risky operation, or handle it manually.',
                attention=reason,
                stop_reason='safety_boundary',
            )
        )
        return 2
    if intent_name == 'preview_artifact':
        code, message = run_preview_artifact_prompt(project, text)
        print(message)
        return code
    if intent_name == 'single_step_edit' and intent.get('execution_mode') == 'direct_docs_apply':
        code, message = run_direct_docs_prompt(project, text, [str(item) for item in intent.get('target_files') or []])
        print(message)
        return code
    if intent_name == 'seed_prompt_execution':
        code, message = run_seed_queue_prompt(project, text, intent)
        print(message)
        return code
    if intent_name == 'project_goal':
        payload = start_or_update_job(project, text, steps=1)
        status = 'Needs attention' if payload.get('status') == 'blocked' else 'Working'
        attention = '' if status == 'Working' else 'An existing running job needs to be stopped before switching goals.'
        print(
            public_report_with_overview(
                project,
                status=status,
                goal=text,
                changed_files=[],
                why=str(intent.get('reason') or 'The prompt describes a project goal.'),
                next_action='Run agent to review progress, or agent continue to move the job forward.',
                attention=attention,
                stop_reason='project_job_started' if status == 'Working' else 'active_job_requires_review',
            )
        )
        return 0 if status == 'Working' else 2
    reason = str(intent.get('reason') or 'No safe target file or project seed prompt was identified.')
    record_unified_job(project, goal=text, status='Needs attention', changed_files=[], attention_reason=reason)
    print(
        public_report_with_overview(
            project,
            status='Needs attention',
            goal=text,
            changed_files=[],
            why=reason,
            next_action='Name the file to change, or add project_beginning_prompt.md and run the prompt again.',
            attention=reason,
            stop_reason='unclear_target',
        )
    )
    return 2


def _run_one_off_prompt(project: Path, text: str, *, allowed_files: list[str] | None = None) -> tuple[int, str]:
    intent = classify_prompt(project, text, allowed_files=allowed_files or [])
    intent_name = str(intent.get('intent') or '')
    if intent_name == 'unsafe_or_needs_confirmation':
        reason = str(intent.get('reason') or 'high-risk operation')
        return 2, one_off_report(
            project,
            status='Needs attention',
            goal=text,
            changed_files=[],
            why='The one-off request asks for an operation that should not run automatically.',
            next_action='Revise the request to remove the risky operation, or handle it manually.',
            attention=reason,
        )
    if intent_name == 'single_step_edit' and intent.get('execution_mode') == 'direct_docs_apply':
        result = apply_docs_patch(
            project, objective=text, target_files=[str(item) for item in intent.get('target_files') or []]
        )
        changed = [str(item) for item in result.get('changed_files') or []]
        blocked = [item for item in result.get('blocked') or [] if isinstance(item, dict)]
        skipped = [item for item in result.get('skipped') or [] if isinstance(item, dict)]
        if blocked and not changed:
            reason = '; '.join(f'{item.get("path")}: {item.get("reason")}' for item in blocked) or 'unsupported target'
            return 2, one_off_report(
                project,
                status='Not applied',
                goal=text,
                changed_files=[],
                why='The requested target is outside the safe documentation area.',
                next_action='Use README.md or a docs/*.md / docs/*.txt file, or run agent for project-level work.',
                attention=reason,
            )
        if changed:
            why = 'The request named safe documentation targets, so Agent applied a bounded one-off document update.'
        elif skipped:
            why = 'The requested document update was already present.'
        else:
            why = str(result.get('summary') or 'No file changes were needed.')
        attention = ''
        if blocked:
            attention = '; '.join(f'{item.get("path")}: {item.get("reason")}' for item in blocked)
        return 0, one_off_report(
            project,
            status='Done',
            goal=text,
            changed_files=changed,
            why=why,
            next_action='Review with git diff, then run agent for the project overview.',
            attention=attention,
        )
    payload = write_preview_artifact(project, objective=text)
    preview_path = str(payload.get('preview_path') or '.zoo-agent/previews/preview.md')
    why = 'You used agent do, so Agent kept this separate from the current project goal.'
    if intent_name in {'seed_prompt_execution', 'project_goal'}:
        why = 'This looks like project-level work; agent do kept it as an independent preview instead of replacing the current project goal.'
    return 0, one_off_report(
        project,
        status='Done',
        goal=text,
        changed_files=[],
        why=why,
        next_action='Open the preview, then use agent "<project goal>" if you want to steer the main project.',
        preview_path=preview_path,
    )


def do_command(args) -> int:
    text = ' '.join(args.input).strip()
    if not text:
        print(
            one_off_report(
                project_root(args.workspace),
                status='Needs attention',
                goal='',
                changed_files=[],
                why='No one-off task was provided.',
                next_action='Run agent do "<one-off task>".',
                attention='missing task',
            )
        )
        return 2
    project = project_root(args.workspace)
    code, message = _run_one_off_prompt(project, text, allowed_files=getattr(args, 'allowed_file', []))
    print(message)
    return code


def ask(args) -> int:
    if args.preview and args.apply:
        print_json(
            user_task_result(
                task=' '.join(args.input).strip(), mode='blocked', result='choose either --preview or --apply, not both'
            )
        )
        return 2
    text = ' '.join(args.input).strip()
    if not text:
        print_json(user_task_result(task='', mode='blocked', result='please describe what you want done'))
        return 2
    project = project_root(args.workspace)
    if not args.preview and not args.apply and not args.allowed_file:
        return run_unified_prompt(args, text)
    mode = 'apply' if args.apply else 'preview'
    ensure_bootstrap_before_run(args)
    selected_backend = str(read_backend_selection(project))
    if mode == 'apply':
        issue = actual_execution_issue(project, selected_backend)
        if issue:
            print_json(user_task_result(task=text, mode='blocked', result=issue))
            return 2
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'pipeline_loop.py'),
        '--workspace',
        str(project),
        '--max-iterations',
        '1',
        '--sandbox',
        'workspace-write',
        '--timeout-seconds',
        '360',
        '--max-retries',
        '2',
        '--backend',
        selected_backend,
    ]
    if mode == 'preview':
        command.append('--dry-run')
    else:
        command.append('--allow-actual')
    for item in args.allowed_file:
        command.extend(['--allowed-file', item])
    command.append(text)
    proc = run_command_capture(command, ROOT)
    stdout = str(proc.get('stdout') or '').strip()
    payload: dict = {}
    if stdout.startswith('{'):
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {}
    if getattr(args, 'debug', False):
        safe_print_text(
            stdout
            if stdout
            else json.dumps(
                {'returncode': proc.get('returncode'), 'stderr': proc.get('stderr', '')}, ensure_ascii=False, indent=2
            )
        )
        return int(proc.get('returncode') or 0)
    if proc.get('returncode') != 0:
        print_json(user_task_result(task=text, mode='blocked', result=pipeline_failure_summary(payload, proc)))
        return int(proc.get('returncode') or 1)
    result = str(payload.get('final_verdict') or ('PREVIEW_READY' if mode == 'preview' else 'APPLIED'))
    if mode == 'preview' and result == 'DRY_RUN_COMPLETE':
        result = 'PREVIEW_READY'
    if mode == 'apply' and result != 'COMPLETED':
        print_json(user_task_result(task=text, mode='blocked', result=f'not applied: {result}'))
        return 1
    if mode == 'apply':
        fallbacks = {str(item) for item in payload.get('fallback_used') or []}
        changed = [str(item) for item in payload.get('changed_files') or []]
        if fallbacks & {'bounded_docs_writer', 'remote_openai_worker'}:
            result = 'Applied via safe docs fallback'
            if changed:
                result = f'{result}: {", ".join(changed)}'
    print_json(user_task_result(task=text, mode=mode, result=result))
    return 0


def undo_command(args) -> int:
    mode = 'apply' if getattr(args, 'apply', False) else 'preview'
    if getattr(args, 'preview', False) and getattr(args, 'apply', False):
        print_json(user_task_result(task='undo', mode='blocked', result='choose either --preview or --apply, not both'))
        return 2
    project = project_root(args.workspace)
    session_result = delegate_capture('session_runtime_engine.py', ['--workspace', str(project), '--undo', '--json'])
    session_payload = parse_json_output(session_result)
    try:
        from job_state_store import sync_job_from_session, write_job_digest

        job = sync_job_from_session(project)
        write_job_digest(project, job)
    except Exception:
        pass
    checkpoint = session_payload.get('checkpoint') if isinstance(session_payload.get('checkpoint'), dict) else {}
    if checkpoint:
        print_json(
            user_task_result(task='undo', mode=mode, result=f'checkpoint available: {checkpoint.get("checkpoint_id")}')
        )
        return 0
    latest = latest_run_id(project)
    if not latest:
        print_json(user_task_result(task='undo', mode=mode, result='nothing to undo'))
        return 0
    if mode == 'preview':
        print_json(user_task_result(task='undo', mode='preview', result='undo preview ready'))
        return 0
    print_json(
        user_task_result(task='undo', mode='blocked', result='automatic undo apply is not available yet; preview only')
    )
    return 2


def config_command(args) -> int:
    if args.config_action == 'backend':
        result = backend_command(argparse.Namespace(backend_action='switch', name=args.name, workspace=args.workspace))
        return result
    print_json({'status': 'failed', 'result': 'unknown config command'})
    return 2


def debug_command(args) -> int:
    if args.debug_action == 'status':
        return status(argparse.Namespace(workspace=args.workspace, run_id='', no_write=True, debug=True))
    if args.debug_action == 'trace':
        project = project_root(args.workspace)
        latest = latest_run_id(project)
        if not latest:
            print_json({'status': 'empty', 'result': 'no trace available'})
            return 0
        trace = project / '.zoo-agent' / 'runs' / latest / 'pipeline' / 'pipeline-loop.json'
        if trace.exists():
            print(trace.read_text(encoding='utf-8'))
            return 0
        print_json({'status': 'missing', 'result': 'trace not found'})
        return 0
    if args.debug_action == 'backend':
        if args.backend_debug_action == 'list':
            return backend_command(argparse.Namespace(backend_action='list', workspace=args.workspace))
        if args.backend_debug_action == 'switch':
            return backend_command(
                argparse.Namespace(backend_action='switch', name=args.name, workspace=args.workspace)
            )
        if args.backend_debug_action == 'health':
            return backend_command(argparse.Namespace(backend_action='health', workspace=args.workspace))
    print_json({'status': 'failed', 'result': 'unknown debug command'})
    return 2
