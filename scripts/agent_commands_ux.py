#!/usr/bin/env python3
"""User interaction command handlers (ask, do, undo, shell, status)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from agent_commands import (
    backend_command,
    goal_command,
    loop_command,
    reroute,
    review,
    rollback,
    run,
)
from agent_utils import (
    active_job_blocks_unified_prompt,
    actual_execution_issue,
    clean_progress,
    delegate_capture,
    ensure_bootstrap_before_run,
    latest_run_id,
    make_run_namespace,
    migrate_legacy_seed_preview_queue,
    one_off_report,
    parse_json_output,
    pipeline_failure_summary,
    print_json,
    public_report_with_overview,
    record_seed_queue_job,
    record_unified_job,
    run_command_capture,
    run_direct_docs_prompt,
    run_preview_artifact_prompt,
    run_seed_queue_prompt,
    safe_print_text,
    user_task_result,
    workspace_arg,
)
from backend_registry import read_backend_selection
from bounded_docs_writer import apply_docs_patch
from job_controller import continue_job, show_job_inbox, start_or_update_job, stop_job
from job_state_store import (
    load_current_job,
)
from preview_artifact_writer import write_preview_artifact
from prompt_intent_router import classify_prompt
from runtime_common import load_json, project_root
from seed_action_queue import load_queue as load_seed_queue
from seed_action_queue import next_pending_action as next_seed_action
from seed_action_queue import run_batch as run_seed_batch


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
    diff_info = session_payload.get('diff') if isinstance(session_payload.get('diff'), dict) else {}

    if checkpoint:
        checkpoint_id = str(checkpoint.get('checkpoint_id') or 'unknown')
        if diff_info.get('available'):
            changed_files = diff_info.get('changed_files') or []
            summary = str(diff_info.get('summary') or f'{len(changed_files)} files changed')
            file_list = changed_files[:20]
            file_hint = f' ({len(changed_files)} total)' if len(changed_files) > 20 else ''
            if mode == 'preview':
                lines = [
                    f'Checkpoint: {checkpoint_id} at {diff_info["checkpoint_commit"]}',
                    f'Changes since checkpoint: {summary}',
                ]
                if file_list:
                    lines.append('Affected files:')
                    for f in file_list:
                        lines.append(f'  - {f}')
                    if file_hint:
                        lines.append(f'  ... and {len(changed_files) - 20} more{file_hint}')
                lines.append('')
                lines.append('To undo: run `agent undo --apply` to restore checkpoint state via git checkout.')
                print('\n'.join(lines))
                return 0
            else:
                # apply mode — will be handled in Task #12
                print_json(
                    user_task_result(
                        task='undo',
                        mode='blocked',
                        result=f'{checkpoint_id}: {summary} ({len(changed_files)} files). Use preview first, then confirm with --yes.',
                    )
                )
                return 2
        else:
            reason = str(diff_info.get('reason') or 'checkpoint commit unreachable')
            print_json(
                user_task_result(task='undo', mode='blocked', result=f'{checkpoint_id} found but cannot undo: {reason}')
            )
            return 2

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
