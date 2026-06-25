#!/usr/bin/env python3
"""Shared utility functions for the agent CLI entry point."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from bounded_docs_writer import apply_docs_patch
from check_project_readiness import analyze_project_readiness
from job_state_store import (
    append_job_event,
    default_job,
    load_current_job,
    save_current_job,
    write_job_digest,
)
from preview_artifact_writer import write_preview_artifact
from project_map_builder import build_project_map, render_markdown
from project_map_schema import map_dir
from project_progress_overview import render_interaction_summary
from runtime_common import load_json, project_root, utc_now, write_json
from seed_action_queue import init_queue as init_seed_queue
from seed_action_queue import load_queue as load_seed_queue
from seed_action_queue import mark_action as mark_seed_action
from seed_action_queue import next_pending_action as next_seed_action
from seed_action_queue import run_batch as run_seed_batch


def ensure_bootstrap_before_run(args) -> None:
    project = project_root(args.workspace)
    if is_bootstrapped(project):
        return
    return


def run_command(command: list[str], cwd: Path) -> int:
    proc = subprocess.run(command, cwd=cwd)
    return proc.returncode


def run_command_capture(command: list[str], cwd: Path) -> dict:
    env = os.environ.copy()
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    env.setdefault('PYTHONUTF8', '1')
    proc = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    return {
        'command': [str(item) for item in command],
        'cwd': str(cwd),
        'returncode': proc.returncode,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def delegate(script_name: str, args_list: list[str]) -> int:
    return run_command([sys.executable, str(ROOT / 'scripts' / script_name), *args_list], ROOT)


def delegate_capture(script_name: str, args_list: list[str]) -> dict:
    return run_command_capture([sys.executable, str(ROOT / 'scripts' / script_name), *args_list], ROOT)


def parse_json_output(result: dict) -> dict:
    raw = str(result.get('stdout') or '{}').strip()
    if not raw.startswith('{'):
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def safe_print_text(text: str) -> None:
    output = f'{text}\n' if not str(text).endswith('\n') else str(text)
    encoding = sys.stdout.encoding or 'utf-8'
    try:
        sys.stdout.write(output)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(output.encode(encoding, errors='replace'))


def print_json(payload: dict) -> None:
    safe_print_text(json.dumps(payload, ensure_ascii=False, indent=2))


def clean_progress(value: object) -> str:
    if isinstance(value, int | float):
        return f'{max(0, min(int(value), 100))}%'
    text = str(value or '').strip()
    if not text:
        return 'unknown'
    return text


def workspace_arg(workspace: str) -> str:
    return str(project_root(workspace))


def bootstrap_lock_path(project: Path) -> Path:
    return project / '.zoo-agent' / 'bootstrap.lock'


def is_bootstrapped(project: Path) -> bool:
    return (project / '.zoo-agent' / 'runtime-v4.json').exists() or bootstrap_lock_path(project).exists()


def is_git_repo(project: Path) -> bool:
    result = run_command_capture(['git', 'rev-parse', '--show-toplevel'], project)
    return result.get('returncode') == 0


def is_empty_project_dir(project: Path) -> bool:
    return not any(item.name not in {'.', '..'} for item in project.iterdir())


def shutil_which(binary: str) -> str:
    from shutil import which

    return which(binary) or ''


def detect_profile(project: Path) -> dict:
    source_roots = [
        name
        for name in ['src', 'app', 'lib', 'packages', 'services', 'backend', 'frontend']
        if (project / name).is_dir()
    ]
    test_roots = [
        name for name in ['tests', 'test', 'spec', 'frontend/tests', 'backend/tests'] if (project / name).is_dir()
    ]
    manifests = [
        name
        for name in ['package.json', 'pyproject.toml', 'requirements.txt', 'go.mod', 'Cargo.toml', 'pom.xml']
        if (project / name).exists()
    ]
    return {
        'schema_version': '1.0',
        'generated_by': 'agent.py bootstrap',
        'generated_at': utc_now(),
        'workspace': str(project),
        'project_kind': 'existing_git_project' if is_git_repo(project) else 'new_or_non_git_project',
        'source_roots': source_roots,
        'test_roots': test_roots,
        'manifests': manifests,
        'runtime_dirs': ['.zoo-agent'],
        'scan_policy': {
            'content_scan': 'metadata_only',
            'secret_contents_read': False,
            'excluded_patterns': [
                '.env',
                '.env.*',
                '**/*.pem',
                '**/*.key',
                'secrets/**',
                'credentials/**',
                '.codex/**',
            ],
        },
    }


def readiness_for_profile(
    project: Path, profile: dict, *, initialized_git: bool = False, base_readiness: dict | None = None
) -> dict:
    readiness = base_readiness or analyze_project_readiness(project)
    blockers = []
    warnings = []
    next_actions = []
    if not is_git_repo(project):
        blockers.append('workspace_is_not_git_repo')
        next_actions.append('Run agent bootstrap --new or initialize git explicitly if this is a new project.')
    if not profile.get('source_roots'):
        warnings.append('source_roots_not_detected')
    if not profile.get('test_roots'):
        warnings.append('test_roots_not_detected')
        next_actions.append('Add or document a test command before relying on merge readiness.')
    if not (project / 'AGENTS.md').exists() and not (project / 'AGENTS.md.new').exists():
        warnings.append('project_instructions_missing')
    legacy = {
        'schema_version': '1.0',
        'generated_by': 'agent.py bootstrap',
        'generated_at': utc_now(),
        'workspace': str(project),
        'safe_for_bootstrap': readiness.get('safe_for_bootstrap', not blockers),
        'safe_for_level_0_1_trial': readiness.get('safe_for_level_0_1_trial', not blockers),
        'safe_for_codex_actual_run': readiness.get('safe_for_codex_actual_run', False),
        'blockers': readiness.get('blockers', []),
        'blocking_issues': blockers,
        'warnings': warnings,
        'next_actions': next_actions or ['Run agent "fix typo in README" for a bounded dry-run/fast-path trial.'],
        'initialized_git': initialized_git,
        'codex_cli_detected': bool(shutil_which('codex')),
    }
    typed_blocking = [item.get('type') for item in readiness.get('blockers', []) if item.get('severity') == 'blocking']
    typed_warnings = [item.get('type') for item in readiness.get('blockers', []) if item.get('severity') == 'warning']
    legacy['blocking_issues'] = sorted(set([*blockers, *[str(item) for item in typed_blocking if item]]))
    legacy['warnings'] = sorted(set([*warnings, *[str(item) for item in typed_warnings if item]]))
    if readiness.get('next_actions'):
        legacy['next_actions'] = readiness['next_actions']
    return legacy


def write_text_if_missing(path: Path, content: str, actions: list[dict], *, reason: str) -> None:
    if path.exists():
        actions.append({'action': 'preserve_existing', 'path': str(path), 'reason': reason})
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    actions.append({'action': 'write_missing', 'path': str(path), 'reason': reason})


def write_gitignore_patch(project: Path, actions: list[dict]) -> None:
    patch = project / '.gitignore.agent.patch'
    if patch.exists():
        actions.append({'action': 'preserve_existing', 'path': str(patch), 'reason': 'gitignore patch already exists'})
        return
    content = '\n'.join(
        [
            '# Proposed agent runtime ignores. Review before applying.',
            '+.zoo-agent/tmp/',
            '+.zoo-agent/worktrees/',
            '+.codex/',
            '+.codex-home/',
            '+__pycache__/',
            '+.pytest_cache/',
            '',
        ]
    )
    patch.write_text(content, encoding='utf-8')
    actions.append(
        {'action': 'write_proposal', 'path': str(patch), 'reason': '.gitignore exists; wrote patch proposal'}
    )


def write_roo_rules_proposal(project: Path, actions: list[dict]) -> None:
    rules_dir = project / '.roo' / 'rules'
    if not rules_dir.exists():
        return
    proposal = project / '.roo' / 'rules.new' / '00-cli-first-agent-runtime.md'
    if proposal.exists():
        actions.append(
            {'action': 'preserve_existing', 'path': str(proposal), 'reason': 'roo rules proposal already exists'}
        )
        return
    proposal.parent.mkdir(parents=True, exist_ok=True)
    proposal.write_text(
        '# CLI-first Agent Runtime Proposal\n\n'
        '- CLI is the primary runtime entrypoint.\n'
        '- Codex CLI is execution backend only.\n'
        '- Do not read secrets or auto-merge/push.\n',
        encoding='utf-8',
    )
    actions.append(
        {'action': 'write_proposal', 'path': str(proposal), 'reason': '.roo/rules exists; wrote .new proposal'}
    )


def write_bootstrap_report(
    project: Path, profile: dict, readiness: dict, actions: list[dict], *, already_bootstrapped: bool, version: str
) -> None:
    lines = [
        '# Agent Bootstrap Report',
        '',
        f'- version: {version}',
        f'- workspace: {project}',
        f'- already_bootstrapped: {str(already_bootstrapped).lower()}',
        f'- safe_for_level_0_1_trial: {str(readiness.get("safe_for_level_0_1_trial")).lower()}',
        f'- blocking_issues: {", ".join(readiness.get("blocking_issues") or []) or "none"}',
        f'- warnings: {", ".join(readiness.get("warnings") or []) or "none"}',
        '',
        '## Detected Profile',
        '',
        f'- source_roots: {", ".join(profile.get("source_roots") or []) or "none"}',
        f'- test_roots: {", ".join(profile.get("test_roots") or []) or "none"}',
        f'- manifests: {", ".join(profile.get("manifests") or []) or "none"}',
        '',
        '## Next Actions',
        '',
    ]
    lines.extend(f'- {item}' for item in readiness.get('next_actions') or [])
    lines.extend(['', '## Actions', ''])
    lines.extend(f'- {item.get("action")}: {item.get("path", "")} ({item.get("reason", "")})' for item in actions)
    path = project / '.zoo-agent' / 'bootstrap-report.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def print_bootstrap_output(report: dict, *, debug: bool = False) -> None:
    if debug:
        print_json(report)
        return
    status = str(report.get('status') or 'unknown')
    if report.get('already_bootstrapped'):
        progress = 'already bootstrapped'
        result = 'ready'
    elif status == 'dry_run':
        progress = 'dry_run'
        result = 'bootstrap dry-run'
    elif status.startswith('blocked') or status.endswith('failed'):
        progress = 'blocked'
        result = status
    else:
        progress = 'ready' if status == 'ready' else 'ready_with_warnings'
        result = status
    print_json({'goal': 'workspace setup', 'progress': progress, 'result': result})


def prepare_bootstrap_workspace(project: Path, args) -> tuple[int, dict]:
    entries = list(project.iterdir())
    git_repo = is_git_repo(project)
    if git_repo:
        return 0, {'status': 'existing_git_repo', 'initialized_git': False}
    if not entries:
        if args.dry_run:
            return 0, {'status': 'would_initialize_new_git_repo', 'initialized_git': False}
        result = run_command_capture(['git', 'init'], project)
        if result.get('returncode') != 0:
            return 20, {'status': 'git_init_failed', 'initialized_git': False, 'git_init': result}
        return 0, {'status': 'initialized_new_git_repo', 'initialized_git': True, 'git_init': result}
    if args.new or args.force_new_project:
        if args.dry_run:
            return 0, {'status': 'would_initialize_non_empty_new_git_repo', 'initialized_git': False}
        result = run_command_capture(['git', 'init'], project)
        if result.get('returncode') != 0:
            return 20, {'status': 'git_init_failed', 'initialized_git': False, 'git_init': result}
        return 0, {'status': 'initialized_non_empty_new_git_repo', 'initialized_git': True, 'git_init': result}
    return 20, {
        'status': 'blocked_non_git_non_empty_directory',
        'initialized_git': False,
        'message': 'Directory is non-empty and is not a git repo. Pass --new or --force-new-project to initialize explicitly.',
    }


def write_onboarding_artifacts(
    project: Path, args, *, initialized_git: bool, already_bootstrapped: bool, base_readiness: dict | None = None
) -> dict:
    actions: list[dict] = []
    base_readiness = base_readiness or analyze_project_readiness(project)
    if initialized_git or args.new or args.force_new_project or not any(project.iterdir()):
        write_text_if_missing(
            project / 'README.md',
            '# New Agent Project\n\nBootstrapped for CLI-first AI coding runtime.\n',
            actions,
            reason='new project README',
        )
        write_text_if_missing(
            project / '.gitignore',
            '\n'.join(
                [
                    '.zoo-agent/tmp/',
                    '.zoo-agent/worktrees/',
                    '.codex/',
                    '.codex-home/',
                    '__pycache__/',
                    '.pytest_cache/',
                    '',
                ]
            ),
            actions,
            reason='new project gitignore',
        )
        write_text_if_missing(
            project / '.zoo-agent' / 'TASKS.md',
            '# Tasks\n\n- [ ] Define the first bounded coding task.\n',
            actions,
            reason='new project task draft',
        )
    elif (project / '.gitignore').exists():
        write_gitignore_patch(project, actions)
    write_roo_rules_proposal(project, actions)
    profile = detect_profile(project)
    readiness = readiness_for_profile(project, profile, initialized_git=initialized_git, base_readiness=base_readiness)
    write_json(project / '.zoo-agent' / 'project-profile.json', profile)
    write_json(project / '.zoo-agent' / 'project-readiness.json', readiness)
    write_bootstrap_report(project, profile, readiness, actions, already_bootstrapped=already_bootstrapped, version='')
    return {'actions': actions, 'project_profile': profile, 'project_readiness': readiness}


def latest_run_id(project: Path) -> str:
    runs = project / '.zoo-agent' / 'runs'
    if not runs.exists():
        return ''
    candidates = [path for path in runs.iterdir() if path.is_dir()]
    if not candidates:
        return ''
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0].name


def make_run_namespace(workspace: str, text: str, *, dry_run: bool = False):
    import argparse

    return argparse.Namespace(
        workspace=workspace,
        input=[text],
        run_id='',
        task_id='',
        goal_id='',
        allowed_file=[],
        denied_file=[],
        test_command=[],
        changed_file_estimate=0,
        fast=False,
        parallel=False,
        governed=False,
        max_workers=2,
        sandbox='workspace-write',
        profile='',
        codex_home='',
        backend='',
        timeout_seconds=360,
        no_output_timeout_seconds=600,
        test_timeout_seconds=0,
        max_retries=0,
        max_iteration=10,
        start_point='HEAD',
        discard_failed_worktree=False,
        ephemeral=False,
        worker_dry_run=False,
        skip_health_check=False,
        allow_ambiguous_fast=False,
        no_execute_governed_workers=False,
        dry_run=dry_run,
        debug=False,
    )


def user_task_result(*, task: str, mode: str, result: str) -> dict:
    return {'task': task, 'mode': mode, 'result': result}


def actual_execution_issue(project: Path, backend: str) -> str:
    normalized = str(backend or '').strip().lower()
    if normalized in {'dry_run', 'dry-run', 'dryrun'}:
        return f'{normalized} backend is preview/test only; switch to an actual code worker or run with --preview'
    if normalized == 'codex':
        try:
            from codex_worker_adapter_hardened import codex_health

            health = codex_health(project)
        except Exception as exc:
            return f'actual execution worker check failed: {type(exc).__name__}; run agent workers --doctor'
        if not health.get('supports_actual_execution'):
            reason = str(health.get('reason') or health.get('health') or 'codex worker unavailable')
            return f'actual execution worker unavailable: {reason}; run agent workers --doctor'
    return ''


def pipeline_failure_summary(payload: dict, proc: dict) -> str:
    if payload:
        verdict = str(payload.get('final_verdict') or payload.get('status') or '').strip()
        reason = str(payload.get('reason') or payload.get('result') or '').strip()
        if verdict and reason:
            return f'{verdict}: {reason}'
        if verdict:
            return verdict
        if reason:
            return reason
    stderr = str(proc.get('stderr') or '').strip()
    if stderr:
        return stderr.splitlines()[-1][:240]
    stdout = str(proc.get('stdout') or '').strip()
    if stdout:
        return stdout.splitlines()[-1][:240]
    return 'could not complete; run agent workers --doctor or agent debug status'


def record_unified_job(
    project: Path,
    *,
    goal: str,
    status: str,
    changed_files: list[str],
    next_action: str = '',
    attention_reason: str = '',
) -> None:
    job_status = (
        'completed'
        if status == 'Done'
        else ('needs_attention' if status in {'Needs attention', 'Not applied'} else 'active')
    )
    job = default_job(project, goal=goal)
    job.update(
        {
            'status': job_status,
            'last_action': 'unified_prompt_entry',
            'last_changed_files': changed_files,
            'next_action': next_action,
            'attention_required': job_status == 'needs_attention',
            'attention_reason': attention_reason,
        }
    )
    save_current_job(project, job)
    append_job_event(
        project,
        'unified_prompt_entry',
        {'job_id': job.get('job_id', ''), 'status': job_status, 'changed_files': changed_files},
    )
    write_job_digest(project, job)


def record_seed_queue_job(project: Path, *, goal: str, queue_result: dict) -> dict:
    remaining = int(queue_result.get('remaining') or 0)
    pending = next_seed_action(project)
    job = load_current_job(project) or default_job(project, goal=goal)
    queue_status = str(queue_result.get('status') or '')
    job_status = 'needs_attention' if queue_status == 'needs_attention' else ('paused' if remaining else 'completed')
    job.update(
        {
            'goal': goal,
            'status': job_status,
            'last_action': str((queue_result.get('action') or {}).get('action_id') or 'seed_action_queue'),
            'last_changed_files': queue_result.get('changed_files') or [],
            'next_action': str(
                pending.get('title')
                or ('Give the next prompt' if not remaining else 'Continue seed prompt action queue')
            ),
            'attention_required': job_status == 'needs_attention',
            'attention_reason': 'seed prompt batch needs attention' if job_status == 'needs_attention' else '',
            'cockpit_path': '.zoo-agent/cockpit/index.html',
            'digest_path': '.zoo-agent/jobs/job_digest.md',
        }
    )
    save_current_job(project, job)
    append_job_event(
        project,
        'seed_queue_step_finished',
        {
            'job_id': job.get('job_id', ''),
            'action_id': (queue_result.get('action') or {}).get('action_id', ''),
            'remaining': remaining,
            'changed_files': queue_result.get('changed_files') or [],
        },
    )
    write_job_digest(project, job)
    return job


def write_project_map_for_prompt(project: Path, goal: str) -> None:
    project_map, state, evidence = build_project_map(project, main_goal=goal)
    out_dir = map_dir(project)
    write_json(out_dir / 'project_map.json', project_map)
    write_json(out_dir / 'project_state.json', state)
    write_json(out_dir / 'map_evidence.json', evidence)
    md = out_dir / 'project_map.md'
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(render_markdown(project_map), encoding='utf-8')


def same_prompt(left: str, right: str) -> bool:
    return ' '.join((left or '').lower().split()) == ' '.join((right or '').lower().split())


def active_job_blocks_unified_prompt(project: Path, prompt: str) -> str:
    existing = load_current_job(project)
    if not existing or existing.get('status') != 'active':
        return ''
    if same_prompt(str(existing.get('goal') or ''), prompt):
        return ''
    return str(existing.get('goal') or 'current project job')


def public_report(
    project: Path,
    *,
    status: str,
    goal: str,
    changed_files: list[str] | None = None,
    why: str = '',
    next_action: str = '',
    attention: str = '',
    stop_reason: str = '',
) -> str:
    return '\n'.join(
        render_interaction_summary(
            project,
            status=status,
            goal=goal,
            changed_files=changed_files or [],
            why=why,
            next_action=next_action,
            attention=attention,
            stop_reason=stop_reason,
        )
    )


def public_report_with_overview(
    project: Path,
    *,
    status: str,
    goal: str,
    changed_files: list[str] | None = None,
    why: str = '',
    next_action: str = '',
    attention: str = '',
    stop_reason: str = '',
) -> str:
    return public_report(
        project,
        status=status,
        goal=goal,
        changed_files=changed_files,
        why=why,
        next_action=next_action,
        attention=attention,
        stop_reason=stop_reason,
    )


def one_off_report(
    project: Path,
    *,
    status: str,
    goal: str,
    changed_files: list[str] | None = None,
    why: str = '',
    next_action: str = '',
    attention: str = '',
    preview_path: str = '',
) -> str:
    return '\n'.join(
        render_interaction_summary(
            project,
            status=status,
            goal=goal,
            changed_files=changed_files or [],
            why=why,
            next_action=next_action,
            attention=attention,
            preview_path=preview_path,
            stop_reason='one_off_task_complete',
            one_off=True,
        )
    )


def run_direct_docs_prompt(
    project: Path, text: str, target_files: list[str], *, project_step: bool = False
) -> tuple[int, str]:
    result = apply_docs_patch(project, objective=text, target_files=target_files)
    changed = [str(item) for item in result.get('changed_files') or []]
    blocked = result.get('blocked') or []
    skipped = result.get('skipped') or []
    if blocked and not changed:
        reason = (
            '; '.join(f'{item.get("path")}: {item.get("reason")}' for item in blocked if isinstance(item, dict))
            or 'unsafe documentation target'
        )
        record_unified_job(project, goal=text, status='Not applied', changed_files=[], attention_reason=reason)
        return 2, public_report_with_overview(
            project,
            status='Not applied',
            goal=text,
            changed_files=[],
            why='The requested target is outside the safe documentation area.',
            next_action='Name a README.md or docs/*.md file, or review the target path.',
            attention=reason,
            stop_reason='unsafe_or_unsupported_target',
        )
    status = 'Working' if project_step else 'Done'
    if changed:
        why = 'The prompt named safe documentation targets, so Agent applied one safe document update.'
    elif skipped:
        why = 'The requested document update was already present.'
    else:
        why = str(result.get('summary') or 'No file changes were needed.')
    if not project_step:
        record_unified_job(
            project,
            goal=text,
            status='Done',
            changed_files=changed,
            next_action='Give another prompt when you want the next change.',
        )
    next_action = (
        'Run agent to review the current job, or give the next prompt.'
        if project_step
        else 'Give another prompt when you want the next change.'
    )
    return 0, public_report_with_overview(
        project,
        status=status,
        goal=text,
        changed_files=changed,
        why=why,
        next_action=next_action,
        stop_reason='reviewable_batch_complete',
    )


def run_seed_queue_prompt(project: Path, text: str, intent: dict[str, object]) -> tuple[int, str]:
    write_project_map_for_prompt(project, text)
    init_seed_queue(
        project,
        goal=text,
        source_file=str(intent.get('seed_file') or 'project_beginning_prompt.md'),
        research='docs/research_workflow.md' in [str(item) for item in intent.get('target_files') or []],
    )
    result = run_seed_batch(project, goal=text, max_steps=3)
    record_seed_queue_job(project, goal=text, queue_result=result)
    changed = [str(item) for item in result.get('changed_files') or []]
    remaining = int(result.get('remaining') or 0)
    status = 'Needs attention' if result.get('status') == 'needs_attention' else 'Done'
    pending = next_seed_action(project)
    next_text = 'agent continue' if pending else 'agent "<next project goal>"'
    why = (
        'Completed the first reviewable project package from the seed prompt.'
        if remaining
        else 'Completed all safe starter actions from the seed prompt.'
    )
    return 0, public_report_with_overview(
        project,
        status=status,
        goal=text,
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


def run_preview_artifact_prompt(project: Path, text: str) -> tuple[int, str]:
    payload = write_preview_artifact(project, objective=text)
    preview_path = str(payload.get('preview_path') or '.zoo-agent/previews/preview.md')
    message = one_off_report(
        project,
        status='Done',
        goal=text,
        changed_files=[],
        why='Generated a temporary local preview without changing the current project goal.',
        next_action=f'Open {preview_path}, then run agent for the project overview.',
        preview_path=preview_path,
    )
    return 0, message


def migrate_legacy_seed_preview_queue(project: Path) -> bool:
    queue = load_seed_queue(project)
    if queue.get('actions'):
        return False
    job = load_current_job(project)
    selected = load_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json')
    if not job or selected.get('action_id') != 'action-seed-docs-bootstrap':
        return False
    if not (selected.get('preview_only') or selected.get('execution_mode') == 'preview'):
        return False
    source_file = str(selected.get('source_file') or 'project_beginning_prompt.md')
    targets = [str(item) for item in selected.get('target_files') or []]
    if not targets or not all((project / target).exists() for target in targets):
        return False
    queue = init_seed_queue(
        project,
        goal=str(job.get('goal') or selected.get('title') or ''),
        source_file=source_file,
        research='docs/research_workflow.md' in targets,
    )
    starter = next(
        (
            item
            for item in queue.get('actions') or []
            if isinstance(item, dict) and item.get('action_id') == 'seed-starter-docs'
        ),
        {},
    )
    if starter:
        mark_seed_action(project, 'seed-starter-docs', status='completed', changed_files=targets)
    append_job_event(
        project, 'legacy_seed_preview_queue_migrated', {'job_id': job.get('job_id', ''), 'source_file': source_file}
    )
    return True
