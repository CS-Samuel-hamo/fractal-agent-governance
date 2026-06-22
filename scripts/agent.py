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

VERSION = (ROOT / 'VERSION').read_text(encoding='utf-8-sig').strip() if (ROOT / 'VERSION').exists() else '1.0.0-alpha.1'

KNOWN_COMMANDS = {
    'alpha',
    'bootstrap',
    'ask',
    'backend',
    'config',
    'cockpit',
    'debug',
    'continue',
    'pipeline',
    'pr',
    'publish',
    'postlaunch',
    'release',
    'run',
    'session',
    'start',
    'status',
    'stop',
    'undo',
    'rollback',
    'reroute',
    'map',
    'standards',
    'workers',
    'review',
    'codex-health',
    'goal',
    'loop',
    'plan-big',
    'decompose',
    'feedback',
    'aggregate',
    'integration-check',
    'goal-loop',
    'global-loop',
    'learning',
    'launch',
}
COMMAND_TYPO_SUGGESTIONS = {
    'rum': '"your task" --preview',
    'runn': '"your task" --preview',
    'rn': '"your task" --preview',
    'stats': 'status',
    'statuz': 'status',
    'pipline': '"your task" --preview',
    'pipeine': '"your task" --preview',
    'bakend': 'config',
    'backnd': 'config',
    'goals': '"your task" --preview',
}

from runtime_common import initialize_loop, load_json, project_root, set_active_goal, utc_now, write_json  # noqa: E402
from check_project_readiness import analyze_project_readiness  # noqa: E402
from update_runtime_metrics import update_metrics  # noqa: E402
from backend_registry import read_backend_selection  # noqa: E402
from job_controller import continue_job, show_job_inbox, start_or_update_job, stop_job, undo_job  # noqa: E402


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
    if isinstance(value, (int, float)):
        return f'{max(0, min(int(value), 100))}%'
    text = str(value or '').strip()
    if not text:
        return 'unknown'
    return text if text.endswith('%') else text


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
        print_bootstrap_output({'status': prepare_report.get('status'), 'workspace': str(project), **prepare_report}, debug=getattr(args, 'debug', False))
        return prepare_code
    if args.dry_run:
        print_bootstrap_output(
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
        print_bootstrap_output(report, debug=getattr(args, 'debug', False))
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
    command = ['--workspace', workspace_arg(args.workspace), '--run-id', args.run_id, '--max-iterations', str(args.max_iterations)]
    if args.goal_id:
        command.extend(['--goal-id', args.goal_id])
    return delegate('run_parent_aggregation_gate.py', command)


def goal_loop(args) -> int:
    command = ['--workspace', workspace_arg(args.workspace), '--run-id', args.run_id, '--max-iterations', str(args.max_iterations)]
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
        result = delegate_capture('session_runtime_engine.py', ['--workspace', str(project), '--mode', args.mode, '--start', goal])
        print(str(result.get('stdout') or '').strip())
        return int(result.get('returncode') or 0)
    payload = start_or_update_job(project, goal, mode=args.mode, max_steps=args.max_steps, backend=args.backend, steps=getattr(args, 'steps', 0))
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
                'result': session_payload.get('result') or 'Session: status: unknown; digest: .zoo-agent/session/session_digest.md; cockpit: .zoo-agent/cockpit/index.html',
            }
        )
        return int(session_result.get('returncode') or 0)
    session = load_json(project / '.zoo-agent' / 'autopilot' / 'session.json')
    progress_payload = load_json(project / '.zoo-agent' / 'autopilot' / 'progress.json')
    cockpit_path = project / '.zoo-agent' / 'cockpit' / 'index.html'
    cockpit_hint = ' Project Cockpit: .zoo-agent/cockpit/index.html' if cockpit_path.exists() else ' Run `agent cockpit` to generate a local Project Cockpit.'
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
    goals = ((payload.get('goal_state') or {}).get('goals') or []) if isinstance(payload.get('goal_state'), dict) else []
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
    print_json({'task': 'project cockpit', 'mode': 'ready', 'result': 'Open: .zoo-agent/cockpit/index.html; Then: agent status, agent continue, agent stop, agent undo'})
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
        labels = ', '.join(str(item.get('worker_type') or item.get('name') or 'worker') for item in workers) or 'none available'
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
                'result': f"Selected: {payload.get('worker_role') or 'Worker'}; routing: .zoo-agent/workers/routing_decision.json",
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
                'result': f"Report: .zoo-agent/learning/cross_project/cross_project_learning_report.md; status: {payload.get('status') or 'unknown'}",
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
                'result': f"Store: .zoo-agent/learning/cross_project; status: {payload.get('status') or 'unknown'}",
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


def run_release_pack(project: Path, *, debug: bool = False, pr_only: bool = False) -> tuple[int, dict]:
    common = ['--workspace', str(project)]
    steps = []
    if not pr_only:
        steps.extend(
            [
                'git_context_detector.py',
                'release_readiness_template_builder.py',
                'github_readiness_detector.py',
                'release_readiness_evaluator.py',
                'release_notes_generator.py',
                'changelog_draft_generator.py',
                'release_action_plan_generator.py',
            ]
        )
    else:
        steps.extend(['git_context_detector.py', 'github_readiness_detector.py', 'release_readiness_evaluator.py'])
    steps.extend(['pr_plan_generator.py', 'pr_draft_generator.py'])

    final_payload: dict = {}
    for script in steps:
        result = delegate_capture(script, common)
        if debug:
            print(str(result.get('stdout') or '').strip())
        if result.get('returncode') != 0:
            return int(result.get('returncode') or 1), {'failed_script': script}
        if script == 'pr_draft_generator.py':
            final_payload = parse_json_output(result)

    first_report = delegate_capture('release_workflow_report_generator.py', common)
    if debug:
        print(str(first_report.get('stdout') or '').strip())
    safety = delegate_capture('github_workflow_safety_gate.py', common)
    if debug:
        print(str(safety.get('stdout') or '').strip())
    if safety.get('returncode') != 0:
        return int(safety.get('returncode') or 1), parse_json_output(safety)
    report = delegate_capture('release_workflow_report_generator.py', common)
    if debug:
        print(str(report.get('stdout') or '').strip())
    if report.get('returncode') != 0:
        return int(report.get('returncode') or 1), parse_json_output(report)
    cockpit = delegate_capture('cockpit_renderer.py', common)
    if debug:
        print(str(cockpit.get('stdout') or '').strip())
    if cockpit.get('returncode') != 0:
        return int(cockpit.get('returncode') or 1), parse_json_output(cockpit)
    final_payload.update(parse_json_output(report))
    return 0, final_payload


def release_command(args) -> int:
    project = project_root(args.workspace)
    if getattr(args, 'dogfood', False):
        result = delegate_capture('release_workflow_dogfood_runner.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        readiness = str(payload.get('readiness_value') or 'NOT_READY')
        print_json(
            {
                'task': 'release workflow dogfood',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': f'Report: .zoo-agent/release_dogfood/release_product_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'safety_check', False):
        result = delegate_capture('github_workflow_safety_gate.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        payload = parse_json_output(result)
        print_json(
            {
                'task': 'release safety check',
                'mode': 'ready' if payload.get('safe') else 'blocked',
                'result': 'Safety report: .zoo-agent/release/github_workflow_safety_report.json',
            }
        )
        return int(result.get('returncode') or 0)
    code, payload = run_release_pack(project, debug=getattr(args, 'debug', False), pr_only=False)
    status = str(payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown')
    print_json(
        {
            'task': 'release workflow',
            'mode': 'ready' if code == 0 else 'blocked',
            'result': f'Release pack: .zoo-agent/release/release_workflow_report.md; status: {status}; next: agent cockpit or agent pr',
        }
    )
    return code


def pr_command(args) -> int:
    project = project_root(args.workspace)
    code, payload = run_release_pack(project, debug=getattr(args, 'debug', False), pr_only=True)
    status = str(payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown')
    print_json(
        {
            'task': 'pr draft',
            'mode': 'ready' if code == 0 else 'blocked',
            'result': f'PR draft: .zoo-agent/release/pr_draft.md; status: {status}',
        }
    )
    return code


def alpha_command(args) -> int:
    project = project_root(args.workspace)
    if getattr(args, 'package', False):
        demo = delegate_capture('demo_fixture_packager.py', ['--workspace', str(project)])
        result = delegate_capture('public_alpha_packager.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(demo.get('stdout') or '').strip())
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or demo.get('returncode') or 0)
        print_json(
            {
                'task': 'public alpha package',
                'mode': 'ready' if result.get('returncode') == 0 and demo.get('returncode') == 0 else 'blocked',
                'result': 'Manifest: .zoo-agent/public_alpha/public_alpha_package_manifest.json',
            }
        )
        return int(result.get('returncode') or demo.get('returncode') or 0)
    if getattr(args, 'audit', False) or getattr(args, 'report', False):
        result = delegate_capture('public_alpha_report_generator.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        readiness = payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown'
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public alpha audit',
                'mode': 'ready' if readiness == 'READY_FOR_100_PUBLIC_ALPHA_RELEASE' else 'blocked',
                'result': f'Report: .zoo-agent/public_alpha/public_alpha_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'public alpha', 'mode': 'blocked', 'result': 'unknown alpha command'})
    return 2


def publish_command(args) -> int:
    project = project_root(args.workspace)
    if getattr(args, 'package', False):
        result = delegate_capture('public_release_packager.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public release package',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': 'Manifest: .zoo-agent/public_release/public_release_package_manifest.json',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'preflight', False):
        result = delegate_capture('public_release_gate.py', ['--workspace', str(project)])
        if result.get('returncode') == 0:
            preflight = delegate_capture('release_tag_preflight.py', ['--workspace', str(project)])
        else:
            preflight = {'returncode': 0, 'stdout': '{}'}
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            print(str(preflight.get('stdout') or '').strip())
            return int(result.get('returncode') or preflight.get('returncode') or 0)
        print_json(
            {
                'task': 'public release preflight',
                'mode': 'ready' if payload.get('recommendation') == 'pass' else 'blocked',
                'result': f"Gate: .zoo-agent/public_release/public_release_gate.json; recommendation: {payload.get('recommendation') or 'unknown'}",
            }
        )
        return int(result.get('returncode') or preflight.get('returncode') or 0)
    if getattr(args, 'report', False):
        result = delegate_capture('public_release_report_generator.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        readiness = payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown'
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public release report',
                'mode': 'ready' if readiness == 'READY_TO_PUBLISH_GITHUB_ALPHA' else 'blocked',
                'result': f'Report: .zoo-agent/public_release/public_release_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'public release', 'mode': 'blocked', 'result': 'unknown publish command'})
    return 2


def launch_command(args) -> int:
    project = project_root(args.workspace)
    if getattr(args, 'package', False):
        result = delegate_capture('public_launch_packager.py', ['--workspace', str(project)])
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public launch package',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': 'Package: .zoo-agent/public_launch/public_launch_package.json',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'smoke', False):
        result = delegate_capture('post_publish_smoke_test.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public launch smoke',
                'mode': 'ready' if payload.get('post_publish_smoke_passed') else 'blocked',
                'result': 'Smoke report: .zoo-agent/public_launch/post_publish_smoke_report.json',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'audit', False):
        result = delegate_capture('public_launch_audit.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public launch audit',
                'mode': 'ready' if payload.get('recommendation') == 'pass' else 'blocked',
                'result': f"Audit: .zoo-agent/public_launch/public_launch_audit.json; recommendation: {payload.get('recommendation') or 'unknown'}",
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'report', False):
        result = delegate_capture('launch_report_generator.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        readiness = payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown'
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'public launch report',
                'mode': 'ready' if readiness == 'READY_FOR_MANUAL_GITHUB_PUBLISH' else 'blocked',
                'result': f'Report: .zoo-agent/public_launch/public_launch_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'public launch', 'mode': 'blocked', 'result': 'unknown launch command'})
    return 2


def postlaunch_command(args) -> int:
    project = project_root(args.workspace)
    if getattr(args, 'verify', False):
        result = delegate_capture('post_publish_remote_verifier.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        mode = 'ready' if payload.get('remote_verification_passed') or payload.get('tree_equal') else 'blocked'
        print_json(
            {
                'task': 'post-launch remote verification',
                'mode': mode,
                'result': 'Report: .zoo-agent/post_launch/remote_publish_verification.json',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'branch_audit', False):
        result = delegate_capture('branch_hygiene_audit.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        recommendation = payload.get('recommendation') or 'unknown'
        print_json(
            {
                'task': 'post-launch branch hygiene',
                'mode': 'ready' if recommendation in {'pass', 'manual_action_needed'} else 'blocked',
                'result': f'Branch report: .zoo-agent/post_launch/branch_hygiene_report.json; recommendation: {recommendation}',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'report', False):
        result = delegate_capture('post_publish_report_generator.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        readiness = payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown'
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'post-launch report',
                'mode': 'ready' if readiness == 'READY_FOR_POST_LAUNCH_FEEDBACK_TRIAGE' else 'blocked',
                'result': f'Report: .zoo-agent/post_launch/post_publish_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'post-launch', 'mode': 'blocked', 'result': 'unknown postlaunch command'})
    return 2


def feedback_command(args) -> int:
    project = project_root(args.workspace)
    if getattr(args, 'triage', False):
        result = delegate_capture('feedback_triage_engine.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        recommendation = payload.get('recommendation') or 'unknown'
        print_json(
            {
                'task': 'feedback triage',
                'mode': 'ready' if recommendation != 'fix_feedback_pipeline' else 'blocked',
                'result': f'Triage report: .zoo-agent/feedback/feedback_triage_report.json; recommendation: {recommendation}',
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'signals', False):
        result = delegate_capture('feedback_signal_classifier.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'feedback signals',
                'mode': 'ready' if result.get('returncode') == 0 else 'blocked',
                'result': f"Signals: .zoo-agent/feedback/feedback_signal_report.json; count: {len(payload.get('signals') or [])}",
            }
        )
        return int(result.get('returncode') or 0)
    if getattr(args, 'report', False):
        result = delegate_capture('post_launch_feedback_report_generator.py', ['--workspace', str(project)])
        payload = parse_json_output(result)
        readiness = payload.get('status') or payload.get('readiness', {}).get('readiness') or 'unknown'
        if getattr(args, 'debug', False):
            print(str(result.get('stdout') or '').strip())
            return int(result.get('returncode') or 0)
        print_json(
            {
                'task': 'feedback report',
                'mode': 'ready' if readiness in {'READY_FOR_104_PATCH_PLANNING', 'COLLECT_MORE_FEEDBACK_FIRST'} else 'blocked',
                'result': f'Report: .zoo-agent/feedback/post_launch_feedback_report.md; readiness: {readiness}',
            }
        )
        return int(result.get('returncode') or 0)
    print_json({'task': 'feedback', 'mode': 'blocked', 'result': 'unknown feedback command'})
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
    print_json({'goal': 'rollback plan', 'progress': progress, 'result': 'rollback ready' if result.get('returncode') == 0 else 'rollback error'})
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
        print_json({'goal': active.get('goal') or f'{len(goals)} goals', 'progress': clean_progress(active.get('progress', 0) if active else 0), 'result': f'{len(goals)} goals'})
        return int(result.get('returncode') or 0)
    if args.goal_action in {'pause', 'resume', 'complete', 'backlog', 'block'}:
        if not args.goal_id:
            print(f'goal {args.goal_action} requires --goal-id.', file=sys.stderr)
            return 2
        result = delegate_capture('goal_state_manager.py', [args.goal_action, '--workspace', workspace_arg(args.workspace), '--goal-id', args.goal_id])
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
        print_json({'goal': goal_payload.get('goal') or 'no active goal', 'progress': 'active' if payload.get('active') else 'inactive', 'result': payload.get('status') or 'unknown'})
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
            parts = shlex.split(line)
        except ValueError as exc:
            print(f'Could not parse command: {exc}')
            continue

        if not parts:
            continue

        command = parts[0]
        try:
            if command == '/status':
                status(argparse.Namespace(workspace=str(project), run_id='', no_write='--no-write' in parts[1:], debug=False))
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
                loop_command(argparse.Namespace(loop_action=action, workspace=str(project), run_id='', max_iterations=5))
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
    if first == 'goal' and len(argv) > 1 and argv[1] not in {
        'set',
        'show',
        'status',
        'clear',
        'list',
        'pause',
        'resume',
        'complete',
        'backlog',
        'block',
        'schedule',
        'conflicts',
    }:
        return ['goal', 'set', *argv[1:]]
    if first not in KNOWN_COMMANDS and not first.startswith('-'):
        return ['ask', *argv]
    return argv


def product_help() -> str:
    return f"""usage: agent "<goal>"
       agent
       agent continue
       agent stop
       agent undo
       agent cockpit
       agent release
       agent pr
       agent "<task>" --preview|--apply

AI Project Operator.
Give it a project. It keeps moving it forward.

Most of the time:
  agent "prepare this project for public release"
  agent

When you want to steer:
  agent continue
  agent stop
  agent undo
  agent cockpit

Compatibility aliases:
  agent start "<project goal>"
  agent status

When preparing release:
  agent release
  agent pr

One-off task:
  agent "fix README typo" --preview
  agent "fix README typo" --apply

examples:
  agent "improve project readiness"
  agent
  agent continue
  agent cockpit
  agent release
  agent pr

version: {VERSION}
"""


def product_subcommand_help(argv: list[str]) -> str:
    if len(argv) == 2 and argv[1] in {'-h', '--help'}:
        command = argv[0]
        if command == 'ask':
            return 'usage: agent "<goal>"\n       agent "<task>" [-f file] --preview|--apply\n\nWithout --preview or --apply, this starts or updates a project job.\n'
        if command == 'undo':
            return 'usage: agent undo [--preview|--apply] [--workspace .]\n\nPreview an undo plan by default.\n'
        if command == 'start':
            return 'usage: agent start "<project goal>" [--mode preview|standard|autopilot]\n\nAlias for agent "<goal>". Next time you can usually run agent "<goal>".\n'
        if command == 'continue':
            return 'usage: agent continue [--workspace .]\n\nContinue the current project session.\n'
        if command == 'stop':
            return 'usage: agent stop [--workspace .]\n\nStop the current project session.\n'
        if command == 'config':
            return 'usage: agent config backend <mock|dry_run|codex>\n\nAdvanced: choose an execution provider.\n'
        if command == 'debug':
            return 'usage: agent debug status|trace|backend ...\n\nAdvanced diagnostics only.\n'
        if command == 'run':
            return 'usage: agent "<task>" [--preview|--apply]\n\nThis compatibility command is hidden from normal use.\n'
        if command == 'pipeline':
            return 'usage: agent "<task>" [--preview|--apply]\n\nThis compatibility command is hidden from normal use.\n'
        if command == 'goal':
            return 'usage: agent "<task>" [--preview|--apply]\n\nGoals are handled automatically in normal use.\n'
        if command == 'status':
            return 'usage: agent status [--workspace .]\n\nAlias for agent. Shows the current Project Job Inbox.\n'
        if command == 'cockpit':
            return 'usage: agent cockpit [--workspace .]\n\nGenerate a local Project Cockpit you can open in your browser.\n'
        if command == 'release':
            return 'usage: agent release [--workspace .]\n\nGenerate a local release workflow pack. No remote publishing action is performed.\n'
        if command == 'pr':
            return 'usage: agent pr [--workspace .]\n\nGenerate a local PR draft. No remote PR is created.\n'
        if command == 'backend':
            return 'usage: agent config backend <mock|dry_run|codex>\n\nAdvanced configuration only.\n'
    return ''


def user_task_result(*, task: str, mode: str, result: str) -> dict:
    return {'task': task, 'mode': mode, 'result': result}


def actual_execution_issue(project: Path, backend: str) -> str:
    normalized = str(backend or '').strip().lower()
    if normalized in {'dry_run', 'dry-run', 'dryrun'}:
        return f'{normalized} backend is preview/test only; switch to an actual code worker or run with --preview'
    if normalized == 'codex':
        try:
            from codex_worker_adapter_hardened import codex_health  # noqa: WPS433

            health = codex_health(project)
        except Exception as exc:  # pragma: no cover - defensive diagnostics only
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


def ask(args) -> int:
    if args.preview and args.apply:
        print_json(user_task_result(task=' '.join(args.input).strip(), mode='blocked', result='choose either --preview or --apply, not both'))
        return 2
    text = ' '.join(args.input).strip()
    if not text:
        print_json(user_task_result(task='', mode='blocked', result='please describe what you want done'))
        return 2
    project = project_root(args.workspace)
    if not args.preview and not args.apply and not args.allowed_file:
        payload = start_or_update_job(project, text)
        print(str(payload.get('message') or '').strip())
        return 0 if payload.get('status') != 'blocked' else 2
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
        safe_print_text(stdout if stdout else json.dumps({'returncode': proc.get('returncode'), 'stderr': proc.get('stderr', '')}, ensure_ascii=False, indent=2))
        return int(proc.get('returncode') or 0)
    if proc.get('returncode') != 0:
        print_json(user_task_result(task=text, mode='blocked', result=pipeline_failure_summary(payload, proc)))
        return int(proc.get('returncode') or 1)
    result = str(payload.get('final_verdict') or ('PREVIEW_READY' if mode == 'preview' else 'APPLIED'))
    if mode == 'preview' and result == 'DRY_RUN_COMPLETE':
        result = 'PREVIEW_READY'
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
        from job_state_store import sync_job_from_session, write_job_digest  # noqa: WPS433

        job = sync_job_from_session(project)
        write_job_digest(project, job)
    except Exception:
        pass
    checkpoint = session_payload.get('checkpoint') if isinstance(session_payload.get('checkpoint'), dict) else {}
    if checkpoint:
        print_json(user_task_result(task='undo', mode=mode, result=f'checkpoint available: {checkpoint.get("checkpoint_id")}'))
        return 0
    latest = latest_run_id(project)
    if not latest:
        print_json(user_task_result(task='undo', mode=mode, result='nothing to undo'))
        return 0
    if mode == 'preview':
        print_json(user_task_result(task='undo', mode='preview', result='undo preview ready'))
        return 0
    print_json(user_task_result(task='undo', mode='blocked', result='automatic undo apply is not available yet; preview only'))
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
            return backend_command(argparse.Namespace(backend_action='switch', name=args.name, workspace=args.workspace))
        if args.backend_debug_action == 'health':
            return backend_command(argparse.Namespace(backend_action='health', workspace=args.workspace))
    print_json({'status': 'failed', 'result': 'unknown debug command'})
    return 2


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if not raw_argv:
        payload = show_job_inbox(project_root('.'))
        print(str(payload.get('message') or '').strip())
        return 0
    if raw_argv in (['-h'], ['--help']):
        print(product_help())
        return 0
    subcommand_help = product_subcommand_help(raw_argv)
    if subcommand_help:
        print(subcommand_help)
        return 0
    suggestion = COMMAND_TYPO_SUGGESTIONS.get(raw_argv[0].lower()) if raw_argv else ''
    if suggestion:
        print_json(user_task_result(task='command help', mode='blocked', result=f'unknown command: {raw_argv[0]}; try: agent {suggestion}'))
        return 2
    raw_argv = normalize_argv(raw_argv)

    parser = argparse.ArgumentParser(prog='agent', description='AI task runner: ask -> preview -> apply.')
    parser.add_argument('--version', action='version', version=f'agent {VERSION}')
    sub = parser.add_subparsers(dest='command', required=True)

    ask_parser = sub.add_parser('ask', help=argparse.SUPPRESS)
    ask_parser.add_argument('input', nargs='*')
    ask_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    ask_parser.add_argument('-f', '--file', '--only', '--allowed-file', dest='allowed_file', action='append', default=[])
    ask_parser.add_argument('--preview', action='store_true')
    ask_parser.add_argument('--apply', action='store_true')
    ask_parser.add_argument('--debug', action='store_true')
    ask_parser.set_defaults(handler=ask)

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
    bootstrap_parser.add_argument('--debug', action='store_true')
    bootstrap_parser.set_defaults(handler=bootstrap)

    run_parser = sub.add_parser('run', help='Run a task and return a concise result.')
    run_parser.add_argument('input', nargs='*')
    run_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    run_parser.add_argument('--run-id', default='')
    run_parser.add_argument('--task-id', default='')
    run_parser.add_argument('--goal-id', default='')
    run_parser.add_argument('-f', '--file', '--only', '--allowed-file', dest='allowed_file', action='append', default=[])
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
    run_parser.add_argument('--backend', default='')
    run_parser.add_argument('--timeout-seconds', type=int, default=360)
    run_parser.add_argument('--no-output-timeout-seconds', type=int, default=600)
    run_parser.add_argument('--test-timeout-seconds', type=int, default=0)
    run_parser.add_argument('--max-retries', type=int, default=0)
    run_parser.add_argument('--max-iteration', type=int, default=10)
    run_parser.add_argument('--start-point', default='HEAD')
    run_parser.add_argument('--discard-failed-worktree', action='store_true')
    run_parser.add_argument('--ephemeral', action='store_true')
    run_parser.add_argument('--worker-dry-run', action='store_true')
    run_parser.add_argument('--skip-health-check', action='store_true')
    run_parser.add_argument('--allow-ambiguous-fast', action='store_true')
    run_parser.add_argument('--no-execute-governed-workers', action='store_true')
    run_parser.add_argument('--legacy-runtime', action='store_true', help='Compatibility/debug only: use the pre-pipeline route_task runtime.')
    run_parser.add_argument('--debug', action='store_true', help='Show full internal runtime output.')
    run_parser.add_argument('--dry-run', action='store_true')
    run_parser.set_defaults(handler=run)

    pipeline_parser = sub.add_parser('pipeline', help='Run a task through the product pipeline and return a result.')
    pipeline_parser.add_argument('input', nargs='*')
    pipeline_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    pipeline_parser.add_argument('--run-id', default='')
    pipeline_parser.add_argument('--task-id', default='')
    pipeline_parser.add_argument('--goal-id', default='')
    pipeline_parser.add_argument('-f', '--file', '--only', '--allowed-file', dest='allowed_file', action='append', default=[])
    pipeline_parser.add_argument('--denied-file', action='append', default=[])
    pipeline_parser.add_argument('--force-path', choices=['', 'fast', 'parallel', 'governed'], default='')
    pipeline_parser.add_argument('--max-iterations', type=int, default=1)
    pipeline_parser.add_argument('--dry-run', action='store_true')
    pipeline_parser.add_argument('--allow-actual', action='store_true')
    pipeline_parser.add_argument('--sandbox', choices=['read-only', 'workspace-write', 'danger-full-access'], default='workspace-write')
    pipeline_parser.add_argument('--codex-home', default='')
    pipeline_parser.add_argument('--backend', default='')
    pipeline_parser.add_argument('--timeout-seconds', type=int, default=360)
    pipeline_parser.add_argument('--max-retries', type=int, default=2)
    pipeline_parser.add_argument('--debug', action='store_true', help='Show full internal runtime output.')
    pipeline_parser.set_defaults(handler=pipeline)

    plan_big_parser = sub.add_parser('plan-big', help=argparse.SUPPRESS)
    plan_big_parser.add_argument('input', nargs='*')
    plan_big_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    plan_big_parser.add_argument('--run-id', default='run-big-task')
    plan_big_parser.add_argument('--goal-id', default='')
    plan_big_parser.set_defaults(handler=plan_big)

    decompose_parser = sub.add_parser('decompose', help=argparse.SUPPRESS)
    decompose_parser.add_argument('input', nargs='*')
    decompose_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    decompose_parser.add_argument('--run-id', default='run-big-task')
    decompose_parser.add_argument('--goal-id', default='')
    decompose_parser.add_argument('--allow-leaf-actual', action='store_true')
    decompose_parser.set_defaults(handler=decompose_big)

    aggregate_parser = sub.add_parser('aggregate', help=argparse.SUPPRESS)
    aggregate_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    aggregate_parser.add_argument('--run-id', required=True)
    aggregate_parser.add_argument('--goal-id', default='')
    aggregate_parser.add_argument('--max-iterations', type=int, default=10)
    aggregate_parser.set_defaults(handler=aggregate_big)

    goal_loop_parser = sub.add_parser('goal-loop', help=argparse.SUPPRESS)
    goal_loop_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    goal_loop_parser.add_argument('--run-id', required=True)
    goal_loop_parser.add_argument('--goal-id', default='')
    goal_loop_parser.add_argument('--max-iterations', type=int, default=10)
    goal_loop_parser.add_argument('--no-advance', action='store_true')
    goal_loop_parser.add_argument('--no-next-goal-suggestions', action='store_true')
    goal_loop_parser.set_defaults(handler=goal_loop)

    global_loop_parser = sub.add_parser('global-loop', help=argparse.SUPPRESS)
    global_loop_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    global_loop_parser.add_argument('--max-iterations', type=int, default=100)
    global_loop_parser.add_argument('--max-continuous-goal-iterations', type=int, default=3)
    global_loop_parser.add_argument('--backend-health', default='')
    global_loop_parser.add_argument('--no-advance', action='store_true')
    global_loop_parser.set_defaults(handler=global_loop)

    integration_parser = sub.add_parser('integration-check', help=argparse.SUPPRESS)
    integration_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    integration_parser.add_argument('--run-id', required=True)
    integration_parser.add_argument('--yes', action='store_true', help='Actually create the isolated integration worktree.')
    integration_parser.set_defaults(handler=integration_check)

    start_parser = sub.add_parser('start', help='Start map-backed project progress.')
    start_parser.add_argument('goal', nargs='*')
    start_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    start_parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='standard')
    start_parser.add_argument('--max-steps', type=int, default=0)
    start_parser.add_argument('--steps', type=int, default=0, help=argparse.SUPPRESS)
    start_parser.add_argument('--backend', default='')
    start_parser.add_argument('--debug', action='store_true')
    start_parser.set_defaults(handler=start_command)

    continue_parser = sub.add_parser('continue', help='Continue the current project session.')
    continue_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    continue_parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='standard')
    continue_parser.add_argument('--max-steps', type=int, default=0)
    continue_parser.add_argument('--steps', type=int, default=0, help=argparse.SUPPRESS)
    continue_parser.add_argument('--backend', default='')
    continue_parser.set_defaults(handler=continue_command)

    stop_parser = sub.add_parser('stop', help='Stop the current project session.')
    stop_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    stop_parser.add_argument('--debug', action='store_true')
    stop_parser.set_defaults(handler=stop_command)

    status_parser = sub.add_parser('status', help='Show workspace runtime status.')
    status_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    status_parser.add_argument('--run-id', default='')
    status_parser.add_argument('--no-write', action='store_true')
    status_parser.add_argument('--debug', action='store_true')
    status_parser.set_defaults(handler=status)

    cockpit_parser = sub.add_parser('cockpit', help='Generate a local Project Cockpit.')
    cockpit_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    cockpit_parser.add_argument('--dogfood', action='store_true', help=argparse.SUPPRESS)
    cockpit_parser.add_argument('--debug', action='store_true')
    cockpit_parser.set_defaults(handler=cockpit_command)

    release_parser = sub.add_parser('release', help='Generate a local release workflow pack.')
    release_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    release_parser.add_argument('--doctor', action='store_true', help=argparse.SUPPRESS)
    release_parser.add_argument('--safety-check', dest='safety_check', action='store_true', help=argparse.SUPPRESS)
    release_parser.add_argument('--dogfood', action='store_true', help=argparse.SUPPRESS)
    release_parser.add_argument('--debug', action='store_true')
    release_parser.set_defaults(handler=release_command)

    pr_parser = sub.add_parser('pr', help='Generate a local PR draft.')
    pr_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    pr_parser.add_argument('--debug', action='store_true')
    pr_parser.set_defaults(handler=pr_command)

    alpha_parser = sub.add_parser('alpha', help=argparse.SUPPRESS)
    alpha_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    alpha_parser.add_argument('--audit', action='store_true')
    alpha_parser.add_argument('--package', action='store_true')
    alpha_parser.add_argument('--report', action='store_true')
    alpha_parser.add_argument('--debug', action='store_true')
    alpha_parser.set_defaults(handler=alpha_command)

    publish_parser = sub.add_parser('publish', help=argparse.SUPPRESS)
    publish_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    publish_parser.add_argument('--preflight', action='store_true')
    publish_parser.add_argument('--package', action='store_true')
    publish_parser.add_argument('--report', action='store_true')
    publish_parser.add_argument('--debug', action='store_true')
    publish_parser.set_defaults(handler=publish_command)

    launch_parser = sub.add_parser('launch', help=argparse.SUPPRESS)
    launch_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    launch_parser.add_argument('--package', action='store_true')
    launch_parser.add_argument('--audit', action='store_true')
    launch_parser.add_argument('--report', action='store_true')
    launch_parser.add_argument('--smoke', action='store_true')
    launch_parser.add_argument('--debug', action='store_true')
    launch_parser.set_defaults(handler=launch_command)

    postlaunch_parser = sub.add_parser('postlaunch', help=argparse.SUPPRESS)
    postlaunch_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    postlaunch_parser.add_argument('--verify', action='store_true')
    postlaunch_parser.add_argument('--branch-audit', dest='branch_audit', action='store_true')
    postlaunch_parser.add_argument('--report', action='store_true')
    postlaunch_parser.add_argument('--debug', action='store_true')
    postlaunch_parser.set_defaults(handler=postlaunch_command)

    feedback_parser = sub.add_parser('feedback', help=argparse.SUPPRESS)
    feedback_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    feedback_parser.add_argument('--triage', action='store_true')
    feedback_parser.add_argument('--report', action='store_true')
    feedback_parser.add_argument('--signals', action='store_true')
    feedback_parser.add_argument('--debug', action='store_true')
    feedback_parser.set_defaults(handler=feedback_command)

    session_parser = sub.add_parser('session', help=argparse.SUPPRESS)
    session_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    session_parser.add_argument('--dogfood', action='store_true')
    session_parser.add_argument('--debug', action='store_true')
    session_parser.set_defaults(handler=session_command)

    workers_parser = sub.add_parser('workers', help=argparse.SUPPRESS)
    workers_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    workers_parser.add_argument('--doctor', action='store_true')
    workers_parser.add_argument('--list', action='store_true')
    workers_parser.add_argument('--route-demo', action='store_true')
    workers_parser.add_argument('--dogfood', action='store_true')
    workers_parser.add_argument('--real-dogfood', dest='real_dogfood', action='store_true')
    workers_parser.add_argument('--debug', action='store_true')
    workers_parser.set_defaults(handler=workers_command)

    learning_parser = sub.add_parser('learning', help=argparse.SUPPRESS)
    learning_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    learning_parser.add_argument('--import', dest='import_artifacts', action='store_true')
    learning_parser.add_argument('--build', action='store_true')
    learning_parser.add_argument('--report', action='store_true')
    learning_parser.add_argument('--doctor', action='store_true')
    learning_parser.add_argument('--dogfood', action='store_true')
    learning_parser.add_argument('--source', default='')
    learning_parser.add_argument('--debug', action='store_true')
    learning_parser.set_defaults(handler=learning_command)

    undo_parser = sub.add_parser('undo', help=argparse.SUPPRESS)
    undo_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    undo_parser.add_argument('--preview', action='store_true')
    undo_parser.add_argument('--apply', action='store_true')
    undo_parser.set_defaults(handler=undo_command)

    rollback_parser = sub.add_parser('rollback', help=argparse.SUPPRESS)
    rollback_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    rollback_parser.add_argument('--run-id', required=True)
    rollback_parser.add_argument('--task-id', required=True)
    rollback_parser.add_argument('--dry-run', action='store_true')
    rollback_parser.add_argument('--yes', action='store_true')
    rollback_parser.add_argument('--confirm-current-branch', action='store_true')
    rollback_parser.add_argument('--debug', action='store_true')
    rollback_parser.set_defaults(handler=rollback)

    reroute_parser = sub.add_parser('reroute', help=argparse.SUPPRESS)
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

    map_parser = sub.add_parser('map', help=argparse.SUPPRESS)
    map_sub = map_parser.add_subparsers(dest='map_action', required=True)
    for action in ['check', 'refresh', 'promote']:
        item = map_sub.add_parser(action)
        item.add_argument('--workspace', '--project', dest='workspace', default='.')
        item.add_argument('--dry-run', action='store_true')
        item.add_argument('--promote-if-missing', action='store_true')
        item.set_defaults(handler=map_command)

    standards_parser = sub.add_parser('standards', help=argparse.SUPPRESS)
    standards_sub = standards_parser.add_subparsers(dest='standards_action', required=True)
    for action in ['check', 'promote']:
        item = standards_sub.add_parser(action)
        item.add_argument('--workspace', '--project', dest='workspace', default='.')
        item.add_argument('--refresh', action='store_true')
        item.add_argument('--dry-run', action='store_true')
        item.set_defaults(handler=standards)

    review_parser = sub.add_parser('review', help=argparse.SUPPRESS)
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

    backend_parser = sub.add_parser('backend', help='List, switch, and check execution backends.')
    backend_sub = backend_parser.add_subparsers(dest='backend_action', required=True)
    backend_list = backend_sub.add_parser('list', help='List available backends.')
    backend_list.add_argument('--workspace', '--project', dest='workspace', default='.')
    backend_list.set_defaults(handler=backend_command)
    backend_switch = backend_sub.add_parser('switch', help='Select the backend for this workspace.')
    backend_switch.add_argument('name')
    backend_switch.add_argument('--workspace', '--project', dest='workspace', default='.')
    backend_switch.set_defaults(handler=backend_command)
    backend_health = backend_sub.add_parser('health', help='Show backend health summary.')
    backend_health.add_argument('--workspace', '--project', dest='workspace', default='.')
    backend_health.set_defaults(handler=backend_command)

    config_parser = sub.add_parser('config', help=argparse.SUPPRESS)
    config_sub = config_parser.add_subparsers(dest='config_action', required=True)
    config_backend = config_sub.add_parser('backend')
    config_backend.add_argument('name')
    config_backend.add_argument('--workspace', '--project', dest='workspace', default='.')
    config_backend.set_defaults(handler=config_command)

    debug_parser = sub.add_parser('debug', help=argparse.SUPPRESS)
    debug_sub = debug_parser.add_subparsers(dest='debug_action', required=True)
    debug_status = debug_sub.add_parser('status')
    debug_status.add_argument('--workspace', '--project', dest='workspace', default='.')
    debug_status.set_defaults(handler=debug_command)
    debug_trace = debug_sub.add_parser('trace')
    debug_trace.add_argument('--workspace', '--project', dest='workspace', default='.')
    debug_trace.set_defaults(handler=debug_command)
    debug_backend = debug_sub.add_parser('backend')
    debug_backend_sub = debug_backend.add_subparsers(dest='backend_debug_action', required=True)
    debug_backend_list = debug_backend_sub.add_parser('list')
    debug_backend_list.add_argument('--workspace', '--project', dest='workspace', default='.')
    debug_backend_list.set_defaults(handler=debug_command)
    debug_backend_switch = debug_backend_sub.add_parser('switch')
    debug_backend_switch.add_argument('name')
    debug_backend_switch.add_argument('--workspace', '--project', dest='workspace', default='.')
    debug_backend_switch.set_defaults(handler=debug_command)
    debug_backend_health = debug_backend_sub.add_parser('health')
    debug_backend_health.add_argument('--workspace', '--project', dest='workspace', default='.')
    debug_backend_health.set_defaults(handler=debug_command)

    goal_parser = sub.add_parser('goal', help='Set or inspect the current goal.')
    goal_sub = goal_parser.add_subparsers(dest='goal_action', required=True)
    goal_set = goal_sub.add_parser('set')
    goal_set.add_argument('goal')
    goal_set.add_argument('--workspace', '--project', dest='workspace', default='.')
    goal_set.add_argument('--goal-id', default='')
    goal_set.add_argument('--success-criteria', action='append', default=[])
    goal_set.add_argument('--constraint', action='append', default=[])
    goal_set.add_argument('--non-goal', action='append', default=[])
    goal_set.add_argument('--risk-tolerance', choices=['low', 'medium', 'high'], default='low')
    goal_set.add_argument('--priority', type=int, default=50)
    goal_set.add_argument('--resource', action='append', default=[])
    goal_set.add_argument('--depends-on', action='append', default=[])
    goal_set.add_argument('--no-activate', action='store_true')
    goal_set.add_argument('--debug', action='store_true')
    goal_set.set_defaults(handler=goal_command)
    for action in ['show', 'status', 'clear', 'list']:
        item = goal_sub.add_parser(action)
        item.add_argument('--workspace', '--project', dest='workspace', default='.')
        item.add_argument('--goal-id', default='')
        item.add_argument('--debug', action='store_true')
        item.set_defaults(handler=goal_command)
    for action in ['pause', 'resume', 'complete', 'backlog', 'block']:
        item = goal_sub.add_parser(action)
        item.add_argument('--workspace', '--project', dest='workspace', default='.')
        item.add_argument('--goal-id', required=True)
        item.add_argument('--debug', action='store_true')
        item.set_defaults(handler=goal_command)
    goal_schedule = goal_sub.add_parser('schedule')
    goal_schedule.add_argument('--workspace', '--project', dest='workspace', default='.')
    goal_schedule.add_argument('--max-continuous-iterations', type=int, default=3)
    goal_schedule.add_argument('--backend-health', default='')
    goal_schedule.add_argument('--multi-goal-mode', action='store_true')
    goal_schedule.set_defaults(handler=goal_command)
    goal_conflicts = goal_sub.add_parser('conflicts')
    goal_conflicts.add_argument('--workspace', '--project', dest='workspace', default='.')
    goal_conflicts.add_argument('--apply', action='store_true')
    goal_conflicts.set_defaults(handler=goal_command)

    loop_parser = sub.add_parser('loop', help=argparse.SUPPRESS)
    loop_sub = loop_parser.add_subparsers(dest='loop_action', required=True)
    for action in ['status', 'reset', 'stop', 'explain']:
        item = loop_sub.add_parser(action)
        item.add_argument('--workspace', '--project', dest='workspace', default='.')
        item.add_argument('--run-id', default='')
        item.add_argument('--max-iterations', type=int, default=5)
        item.set_defaults(handler=loop_command)
    loop_set = loop_sub.add_parser('set')
    loop_set.add_argument('--workspace', '--project', dest='workspace', default='.')
    loop_set.add_argument('--run-id', default='')
    loop_set.add_argument('--max-iterations', type=int, default=5)
    loop_set.set_defaults(handler=loop_command)

    health_parser = sub.add_parser('codex-health', help=argparse.SUPPRESS)
    health_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    health_parser.add_argument('--mode', choices=['quick', 'full'], default='full')
    health_parser.add_argument('--codex-home', default=os.environ.get('CODEX_HOME', ''))
    health_parser.add_argument('--timeout-seconds', type=int, default=240)
    health_parser.add_argument('--no-output-timeout-seconds', type=int, default=120)
    health_parser.add_argument('--skip-real-codex', action='store_true')
    health_parser.set_defaults(handler=codex_health)

    args = parser.parse_args(raw_argv)
    if args.command in {'run', 'pipeline'} and not ' '.join(args.input).strip():
        print('Missing task input.', file=sys.stderr)
        return 2
    return args.handler(args)


if __name__ == '__main__':
    raise SystemExit(main())
