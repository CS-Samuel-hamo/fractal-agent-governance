#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

VERSION = '0.4.2-delivery-baseline-hardening'

KNOWN_COMMANDS = {
    'bootstrap',
    'run',
    'status',
    'rollback',
    'reroute',
    'map',
    'standards',
    'review',
}

from runtime_common import initialize_loop, load_json, project_root, set_active_goal, utc_now, write_json  # noqa: E402
from check_project_readiness import analyze_project_readiness  # noqa: E402
from update_runtime_metrics import update_metrics  # noqa: E402


def run_command(command: list[str], cwd: Path) -> int:
    proc = subprocess.run(command, cwd=cwd)
    return proc.returncode


def run_command_capture(command: list[str], cwd: Path) -> dict:
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


def delegate(script_name: str, args_list: list[str]) -> int:
    return run_command([sys.executable, str(ROOT / 'scripts' / script_name), *args_list], ROOT)


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


def detect_profile(project: Path) -> dict:
    source_roots = [name for name in ['src', 'app', 'lib', 'packages', 'services', 'backend', 'frontend'] if (project / name).is_dir()]
    test_roots = [name for name in ['tests', 'test', 'spec', 'frontend/tests', 'backend/tests'] if (project / name).is_dir()]
    manifests = [name for name in ['package.json', 'pyproject.toml', 'requirements.txt', 'go.mod', 'Cargo.toml', 'pom.xml'] if (project / name).exists()]
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
            'excluded_patterns': ['.env', '.env.*', '**/*.pem', '**/*.key', 'secrets/**', 'credentials/**', '.codex/**'],
        },
    }


def readiness_for_profile(project: Path, profile: dict, *, initialized_git: bool = False, base_readiness: dict | None = None) -> dict:
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


def shutil_which(binary: str) -> str:
    from shutil import which

    return which(binary) or ''


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
    actions.append({'action': 'write_proposal', 'path': str(patch), 'reason': '.gitignore exists; wrote patch proposal'})


def write_roo_rules_proposal(project: Path, actions: list[dict]) -> None:
    rules_dir = project / '.roo' / 'rules'
    if not rules_dir.exists():
        return
    proposal = project / '.roo' / 'rules.new' / '00-cli-first-agent-runtime.md'
    if proposal.exists():
        actions.append({'action': 'preserve_existing', 'path': str(proposal), 'reason': 'roo rules proposal already exists'})
        return
    proposal.parent.mkdir(parents=True, exist_ok=True)
    proposal.write_text(
        '# CLI-first Agent Runtime Proposal\n\n'
        '- CLI is the primary runtime entrypoint.\n'
        '- Codex CLI is execution backend only.\n'
        '- Do not read secrets or auto-merge/push.\n',
        encoding='utf-8',
    )
    actions.append({'action': 'write_proposal', 'path': str(proposal), 'reason': '.roo/rules exists; wrote .new proposal'})


def write_bootstrap_report(project: Path, profile: dict, readiness: dict, actions: list[dict], *, already_bootstrapped: bool) -> None:
    lines = [
        '# Agent Bootstrap Report',
        '',
        f'- version: {VERSION}',
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


def write_onboarding_artifacts(project: Path, args, *, initialized_git: bool, already_bootstrapped: bool, base_readiness: dict | None = None) -> dict:
    actions: list[dict] = []
    base_readiness = base_readiness or analyze_project_readiness(project)
    if initialized_git or args.new or args.force_new_project or not any(project.iterdir()):
        write_text_if_missing(project / 'README.md', '# New Agent Project\n\nBootstrapped for CLI-first AI coding runtime.\n', actions, reason='new project README')
        write_text_if_missing(
            project / '.gitignore',
            '\n'.join(['.zoo-agent/tmp/', '.zoo-agent/worktrees/', '.codex/', '.codex-home/', '__pycache__/', '.pytest_cache/', '']) ,
            actions,
            reason='new project gitignore',
        )
        write_text_if_missing(project / '.zoo-agent' / 'TASKS.md', '# Tasks\n\n- [ ] Define the first bounded coding task.\n', actions, reason='new project task draft')
    elif (project / '.gitignore').exists():
        write_gitignore_patch(project, actions)

    write_roo_rules_proposal(project, actions)
    profile = detect_profile(project)
    readiness = readiness_for_profile(project, profile, initialized_git=initialized_git, base_readiness=base_readiness)
    write_json(project / '.zoo-agent' / 'project-profile.json', profile)
    write_json(project / '.zoo-agent' / 'project-readiness.json', readiness)
    write_bootstrap_report(project, profile, readiness, actions, already_bootstrapped=already_bootstrapped)
    return {'actions': actions, 'project_profile': profile, 'project_readiness': readiness}


def bootstrap(args) -> int:
    project = project_root(args.workspace)
    marker_path = project / '.zoo-agent' / 'runtime-v4.json'
    lock_path = bootstrap_lock_path(project)
    prepare_code, prepare_report = prepare_bootstrap_workspace(project, args)
    if prepare_code != 0:
        print(json.dumps({'status': prepare_report.get('status'), 'workspace': str(project), **prepare_report}, ensure_ascii=False, indent=2))
        return prepare_code
    if args.dry_run:
        print(
            json.dumps(
                {
                    'status': 'dry_run',
                    'workspace': str(project),
                    'version': VERSION,
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
                ensure_ascii=False,
                indent=2,
            )
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
    if lock_path.exists() and not args.force and not args.refresh_instructions and not args.dry_run and not missing_artifacts:
        report = {
            'status': 'already_bootstrapped',
            'workspace': str(project),
            'runtime_marker': str(marker_path),
            'lock': str(lock_path),
            'already_bootstrapped': True,
            'missing_artifacts': missing_artifacts,
            'message': 'already bootstrapped; bootstrap.lock exists and no project files were overwritten.',
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    already_bootstrapped = marker_path.exists() and not args.force
    if already_bootstrapped:
        marker = load_json(marker_path)
        goal = {'goal_id': args.goal_id or marker.get('goal_id', ''), '_path': ''}
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
        command = [sys.executable, str(ROOT / 'scripts' / 'agent_bootstrap.py'), '--project', str(project), '--mode', args.mode]
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
    instruction_result = delegate('init_project_instructions.py', instruction_args)

    map_args = ['--workspace', str(project), '--refresh', '--promote-if-missing']
    if args.dry_run:
        map_args.append('--dry-run')
    map_result = delegate('check_project_map_alignment.py', map_args)
    onboarding = write_onboarding_artifacts(
        project,
        args,
        initialized_git=bool(prepare_report.get('initialized_git')),
        already_bootstrapped=already_bootstrapped,
        base_readiness=initial_readiness,
    )

    report = {
        'status': 'ready' if legacy_result in {None, 0} and instruction_result == 0 and map_result in {0, 10} else 'ready_with_bootstrap_warnings',
        'version': VERSION,
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
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'ready' else 10


def ensure_bootstrap_before_run(args) -> None:
    project = project_root(args.workspace)
    if is_bootstrapped(project):
        return

    print('Project not bootstrapped. Bootstrap now? yes/no')
    try:
        answer = input().strip().lower()
    except EOFError:
        answer = 'no'

    if answer in {'y', 'yes'}:
        result = delegate('agent.py', ['bootstrap', '--workspace', str(project)])
        if result != 0:
            raise SystemExit(result)
        return

    print('WARNING: running one-off without project bootstrap; runtime evidence may be incomplete.')


def run(args) -> int:
    ensure_bootstrap_before_run(args)
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'route_task.py'),
        '--workspace',
        workspace_arg(args.workspace),
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
    for flag, value in [
        ('--changed-file-estimate', args.changed_file_estimate),
        ('--max-workers', args.max_workers),
        ('--timeout-seconds', args.timeout_seconds),
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


def status(args) -> int:
    command = ['--workspace', workspace_arg(args.workspace)]
    if args.run_id:
        command.extend(['--run-id', args.run_id])
    if args.no_write:
        command.append('--no-write')
    return delegate('runtime_status.py', command)


def rollback(args) -> int:
    command = ['--workspace', workspace_arg(args.workspace), '--run-id', args.run_id, '--task-id', args.task_id]
    if args.dry_run or not args.yes:
        command.append('--dry-run')
    if args.yes:
        command.append('--yes')
    if args.confirm_current_branch:
        command.append('--confirm-current-branch')
    return delegate('rollback_task.py', command)


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


def latest_run_id(project: Path) -> str:
    runs = project / '.zoo-agent' / 'runs'
    if not runs.exists():
        return ''
    candidates = [path for path in runs.iterdir() if path.is_dir()]
    if not candidates:
        return ''
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0].name


def make_run_namespace(workspace: str, text: str, *, dry_run: bool = False):
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
        timeout_seconds=360,
        test_timeout_seconds=0,
        max_retries=0,
        max_iteration=10,
        start_point='HEAD',
        discard_failed_worktree=False,
        ephemeral=False,
        worker_dry_run=False,
        allow_ambiguous_fast=False,
        no_execute_governed_workers=False,
        dry_run=dry_run,
    )


def interactive_help() -> str:
    return '\n'.join(
        [
            'Commands:',
            '  natural language       Run as: agent run <input>',
            '  /status [--no-write]   Show runtime status',
            '  /review <run-id>       Run governance review',
            '  /reroute <run-id> <task-id> <fast|parallel|governed>',
            '  /rollback <run-id> <task-id> [--yes]',
            '  /exit                  Leave interactive mode',
            '  /help                  Show this help',
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
            parts = shlex.split(line)
        except ValueError as exc:
            print(f'Could not parse command: {exc}')
            continue

        if not parts:
            continue

        command = parts[0]
        try:
            if command == '/status':
                status(argparse.Namespace(workspace=str(project), run_id='', no_write='--no-write' in parts[1:]))
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
            elif command.startswith('/'):
                print('Unknown command. Use /help.')
            else:
                run(make_run_namespace(str(project), line, dry_run=dry_run))
        except subprocess.CalledProcessError as exc:
            print(f'Command failed with exit code {exc.returncode}')


def normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    first = argv[0]
    if first in {'-h', '--help'}:
        return argv
    if first not in KNOWN_COMMANDS and not first.startswith('-'):
        return ['run', *argv]
    return argv


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if not raw_argv:
        return interactive_shell('.')
    raw_argv = normalize_argv(raw_argv)

    parser = argparse.ArgumentParser(prog='agent', description='CLI-first AI Agent Runtime v4.0.')
    parser.add_argument('--version', action='version', version=f'agent {VERSION}')
    sub = parser.add_subparsers(dest='command', required=True)

    bootstrap_parser = sub.add_parser('bootstrap', help='Initialize CLI-first runtime state once.')
    bootstrap_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    bootstrap_parser.add_argument('--goal', default='')
    bootstrap_parser.add_argument('--goal-id', default='')
    bootstrap_parser.add_argument('--success-criteria', action='append', default=[])
    bootstrap_parser.add_argument('--constraint', action='append', default=[])
    bootstrap_parser.add_argument('--max-iteration', type=int, default=10)
    bootstrap_parser.add_argument('--with-project-bootstrap', action='store_true')
    bootstrap_parser.add_argument('--mode', choices=['auto', 'existing', 'new'], default='auto')
    bootstrap_parser.add_argument('--new', action='store_true', help='Explicitly initialize a non-empty non-git directory as a new project.')
    bootstrap_parser.add_argument('--force-new-project', action='store_true', help='Explicitly allow git init for a non-empty non-git directory.')
    bootstrap_parser.add_argument('--codex-home', default='')
    bootstrap_parser.add_argument('--dry-run', action='store_true')
    bootstrap_parser.add_argument('--force', action='store_true')
    bootstrap_parser.add_argument('--refresh-instructions', action='store_true')
    bootstrap_parser.set_defaults(handler=bootstrap)

    run_parser = sub.add_parser('run', help='Run a task through the CLI-first router.')
    run_parser.add_argument('input', nargs='*')
    run_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    run_parser.add_argument('--run-id', default='')
    run_parser.add_argument('--task-id', default='')
    run_parser.add_argument('--goal-id', default='')
    run_parser.add_argument('--allowed-file', action='append', default=[])
    run_parser.add_argument('--denied-file', action='append', default=[])
    run_parser.add_argument('--test-command', action='append', default=[])
    run_parser.add_argument('--changed-file-estimate', type=int, default=0)
    run_parser.add_argument('--fast', action='store_true')
    run_parser.add_argument('--parallel', action='store_true')
    run_parser.add_argument('--governed', action='store_true')
    run_parser.add_argument('--max-workers', type=int, default=2)
    run_parser.add_argument('--sandbox', default='workspace-write')
    run_parser.add_argument('--profile', default='')
    run_parser.add_argument('--codex-home', default='')
    run_parser.add_argument('--timeout-seconds', type=int, default=360)
    run_parser.add_argument('--test-timeout-seconds', type=int, default=0)
    run_parser.add_argument('--max-retries', type=int, default=0)
    run_parser.add_argument('--max-iteration', type=int, default=10)
    run_parser.add_argument('--start-point', default='HEAD')
    run_parser.add_argument('--discard-failed-worktree', action='store_true')
    run_parser.add_argument('--ephemeral', action='store_true')
    run_parser.add_argument('--worker-dry-run', action='store_true')
    run_parser.add_argument('--allow-ambiguous-fast', action='store_true')
    run_parser.add_argument('--no-execute-governed-workers', action='store_true')
    run_parser.add_argument('--dry-run', action='store_true')
    run_parser.set_defaults(handler=run)

    status_parser = sub.add_parser('status', help='Summarize runtime, run, map, metrics, and gate state.')
    status_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    status_parser.add_argument('--run-id', default='')
    status_parser.add_argument('--no-write', action='store_true')
    status_parser.set_defaults(handler=status)

    rollback_parser = sub.add_parser('rollback', help='Discard managed worktrees for a task and release task locks.')
    rollback_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    rollback_parser.add_argument('--run-id', required=True)
    rollback_parser.add_argument('--task-id', required=True)
    rollback_parser.add_argument('--dry-run', action='store_true')
    rollback_parser.add_argument('--yes', action='store_true')
    rollback_parser.add_argument('--confirm-current-branch', action='store_true')
    rollback_parser.set_defaults(handler=rollback)

    reroute_parser = sub.add_parser('reroute', help='Reroute a previous task through fast, parallel, or governed path.')
    reroute_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    reroute_parser.add_argument('--run-id', required=True)
    reroute_parser.add_argument('--task-id', required=True)
    reroute_parser.add_argument('--path', required=True, choices=['fast', 'parallel', 'governed'])
    reroute_parser.add_argument('--new-run-id', default='')
    reroute_parser.add_argument('--new-task-id', default='')
    reroute_parser.add_argument('--input-text', default='')
    reroute_parser.add_argument('--goal-id', default='')
    reroute_parser.add_argument('--codex-home', default='')
    reroute_parser.add_argument('--profile', default='')
    reroute_parser.add_argument('--timeout-seconds', type=int, default=360)
    reroute_parser.add_argument('--worker-dry-run', action='store_true')
    reroute_parser.add_argument('--no-execute-governed-workers', action='store_true')
    reroute_parser.add_argument('--discard-failed-worktree', action='store_true')
    reroute_parser.add_argument('--dry-run', action='store_true')
    reroute_parser.set_defaults(handler=reroute)

    map_parser = sub.add_parser('map', help='Check, refresh, or promote project-map alignment.')
    map_sub = map_parser.add_subparsers(dest='map_action', required=True)
    for action in ['check', 'refresh', 'promote']:
        item = map_sub.add_parser(action)
        item.add_argument('--workspace', '--project', dest='workspace', default='.')
        item.add_argument('--dry-run', action='store_true')
        item.add_argument('--promote-if-missing', action='store_true')
        item.set_defaults(handler=map_command)

    standards_parser = sub.add_parser('standards', help='Check or promote project instruction/code-standard proposals.')
    standards_sub = standards_parser.add_subparsers(dest='standards_action', required=True)
    for action in ['check', 'promote']:
        item = standards_sub.add_parser(action)
        item.add_argument('--workspace', '--project', dest='workspace', default='.')
        item.add_argument('--refresh', action='store_true')
        item.add_argument('--dry-run', action='store_true')
        item.set_defaults(handler=standards)

    review_parser = sub.add_parser('review', help='Run evidence closure checks for a runtime run.')
    review_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    review_parser.add_argument('--run-id', default='')
    review_parser.add_argument('--governance-only', action='store_true')
    review_parser.add_argument('--allow-missing-tests', action='store_true')
    review_parser.add_argument('--allow-open-risks', action='store_true')
    review_parser.add_argument('--allow-task-board-warnings', action='store_true')
    review_parser.add_argument('--allow-project-readiness-blocks', action='store_true')
    review_parser.add_argument('--allow-architecture-blocks', action='store_true')
    review_parser.add_argument('--accept-parent-aggregation', action='store_true')
    review_parser.set_defaults(handler=review)

    args = parser.parse_args(raw_argv)
    if args.command == 'run' and not ' '.join(args.input).strip():
        print('Missing task input.', file=sys.stderr)
        return 2
    return args.handler(args)


if __name__ == '__main__':
    raise SystemExit(main())
