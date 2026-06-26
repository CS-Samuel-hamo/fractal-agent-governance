#!/usr/bin/env python3
"""CLI entry point for the AI Project Operator.

This module is the thin entry point for the `agent` command. It sets up
argument parsing, normalizes user input, and delegates to command handlers
in agent_commands.py. Shared utilities live in agent_utils.py.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from agent_commands import (
    audit_command,
    backend_command,
    config_command,
    learning_command,
    map_command,
    reroute,
    rollback,
    session_command,
    standards,
    stats_command,
    workers_command,
)
from agent_commands_goal import (
    codex_health,
    goal_command,
    loop_command,
    review,
)
from agent_commands_release import (
    alpha_command,
    feedback_command,
    launch_command,
    postlaunch_command,
    pr_command,
    publish_command,
    release_command,
)
from agent_commands_session import (
    aggregate_big,
    bootstrap,
    decompose_big,
    global_loop,
    goal_loop,
    integration_check,
    pipeline,
    plan_big,
    run,
)
from agent_commands_ux import (
    ask,
    cockpit_command,
    continue_command,
    debug_command,
    do_command,
    start_command,
    status,
    stop_command,
    undo_command,
)
from agent_utils import print_json, user_task_result
from runtime_common import project_root

try:
    from importlib.metadata import version as _pkg_ver

    VERSION = _pkg_ver('zoo-agent-runtime')
except Exception:
    VERSION = (
        (ROOT / 'VERSION').read_text(encoding='utf-8-sig').strip() if (ROOT / 'VERSION').exists() else '1.0.0-alpha.1'
    )

KNOWN_COMMANDS = {
    'alpha',
    'bootstrap',
    'ask',
    'backend',
    'config',
    'cockpit',
    'debug',
    'do',
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
    'aggregate',
    'integration-check',
    'goal-loop',
    'global-loop',
    'learning',
    'launch',
    'feedback',
    'stats',
    'audit',
}

COMMAND_TYPO_SUGGESTIONS = {
    'rum': '"your task"',
    'runn': '"your task"',
    'rn': '"your task"',
    'statuz': 'status',
    'pipline': '"your task"',
    'pipeine': '"your task"',
    'bakend': 'config',
    'backnd': 'config',
    'goals': '"your task"',
}


def normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    first = argv[0]
    if first in {'-h', '--help'}:
        return argv
    if (
        first == 'goal'
        and len(argv) > 1
        and argv[1]
        not in {
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
        }
    ):
        return ['goal', 'set', *argv[1:]]
    if first not in KNOWN_COMMANDS and not first.startswith('-'):
        return ['ask', *argv]
    return argv


def product_help() -> str:
    return f"""usage: agent "<prompt>"
       agent do "<one-off task>"
       agent
       agent continue
       agent undo
       agent cockpit

AI Project Operator.
Give it a project prompt. It understands, executes a safe step, and reports back.

Most of the time:
  agent "prepare this project for public release"
  agent

For independent tasks that should not replace the current project goal:
  agent do "explain how this workflow is wired"
  agent do "extend docs/research_workflow.md with evidence and validation steps"

When you want to steer:
  agent continue
  agent undo
  agent cockpit

Compatibility aliases:
  agent start "<project goal>"
  agent status

Advanced:
  agent "<task>" --preview
  agent "<task>" --apply
  agent release
  agent pr
  ask -> preview -> apply

examples:
  agent "read and execute project_beginning_prompt.md"
  agent do "show me a temporary overview without changing the project"
  agent "fix README typo"
  agent
  agent continue
  agent cockpit

version: {VERSION}
"""


def product_subcommand_help(argv: list[str]) -> str:
    if len(argv) == 2 and argv[1] in {'-h', '--help'}:
        command = argv[0]
        if command == 'ask':
            return 'usage: agent "<prompt>"\n       agent "<task>" [-f file] --preview|--apply\n\nWithout --preview or --apply, Agent executes one safe step when possible.\n'
        if command == 'do':
            return 'usage: agent do "<one-off task>" [--workspace .]\n\nRun an independent task without replacing the current project job.\n'
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
            return (
                'usage: agent "<task>" [--preview|--apply]\n\nThis compatibility command is hidden from normal use.\n'
            )
        if command == 'pipeline':
            return (
                'usage: agent "<task>" [--preview|--apply]\n\nThis compatibility command is hidden from normal use.\n'
            )
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


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)

    if not raw_argv:
        from job_controller import show_job_inbox

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
        print_json(
            user_task_result(
                task='command help', mode='blocked', result=f'unknown command: {raw_argv[0]}; try: agent {suggestion}'
            )
        )
        return 2

    raw_argv = normalize_argv(raw_argv)

    parser = argparse.ArgumentParser(prog='agent', description='AI task runner: ask -> preview -> apply.')
    parser.add_argument('--version', action='version', version=f'agent {VERSION}')
    sub = parser.add_subparsers(dest='command', required=True)

    # -- ask (default route for bare prompts)
    ask_parser = sub.add_parser('ask', help=argparse.SUPPRESS)
    ask_parser.add_argument('input', nargs='*')
    ask_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    ask_parser.add_argument(
        '-f', '--file', '--only', '--allowed-file', dest='allowed_file', action='append', default=[]
    )
    ask_parser.add_argument('--preview', action='store_true')
    ask_parser.add_argument('--apply', action='store_true')
    ask_parser.add_argument('--debug', action='store_true')
    ask_parser.set_defaults(handler=ask)

    # -- do
    do_parser = sub.add_parser('do', help='Run an independent one-off task.')
    do_parser.add_argument('input', nargs='*')
    do_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    do_parser.add_argument('-f', '--file', '--only', '--allowed-file', dest='allowed_file', action='append', default=[])
    do_parser.set_defaults(handler=do_command)

    # -- bootstrap
    bootstrap_parser = sub.add_parser('bootstrap', help='Initialize CLI-first runtime state once.')
    bootstrap_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    bootstrap_parser.add_argument('--goal', default='')
    bootstrap_parser.add_argument('--goal-id', default='')
    bootstrap_parser.add_argument('--success-criteria', action='append', default=[])
    bootstrap_parser.add_argument('--constraint', action='append', default=[])
    bootstrap_parser.add_argument('--max-iteration', type=int, default=10)
    bootstrap_parser.add_argument('--with-project-bootstrap', action='store_true')
    bootstrap_parser.add_argument('--mode', choices=['auto', 'existing', 'new'], default='auto')
    bootstrap_parser.add_argument(
        '--new', action='store_true', help='Explicitly initialize a non-empty non-git directory as a new project.'
    )
    bootstrap_parser.add_argument(
        '--force-new-project', action='store_true', help='Explicitly allow git init for a non-empty non-git directory.'
    )
    bootstrap_parser.add_argument('--codex-home', default='')
    bootstrap_parser.add_argument('--dry-run', action='store_true')
    bootstrap_parser.add_argument('--force', action='store_true')
    bootstrap_parser.add_argument('--refresh-instructions', action='store_true')
    bootstrap_parser.add_argument('--debug', action='store_true')
    bootstrap_parser.set_defaults(handler=bootstrap)

    # -- run
    run_parser = sub.add_parser('run', help='Run a task and return a concise result.')
    run_parser.add_argument('input', nargs='*')
    run_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    run_parser.add_argument('--run-id', default='')
    run_parser.add_argument('--task-id', default='')
    run_parser.add_argument('--goal-id', default='')
    run_parser.add_argument(
        '-f', '--file', '--only', '--allowed-file', dest='allowed_file', action='append', default=[]
    )
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
    run_parser.add_argument(
        '--legacy-runtime',
        action='store_true',
        help='Compatibility/debug only: use the pre-pipeline route_task runtime.',
    )
    run_parser.add_argument('--debug', action='store_true', help='Show full internal runtime output.')
    run_parser.add_argument('--dry-run', action='store_true')
    run_parser.set_defaults(handler=run)

    # -- pipeline
    pipeline_parser = sub.add_parser('pipeline', help='Run a task through the product pipeline and return a result.')
    pipeline_parser.add_argument('input', nargs='*')
    pipeline_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    pipeline_parser.add_argument('--run-id', default='')
    pipeline_parser.add_argument('--task-id', default='')
    pipeline_parser.add_argument('--goal-id', default='')
    pipeline_parser.add_argument(
        '-f', '--file', '--only', '--allowed-file', dest='allowed_file', action='append', default=[]
    )
    pipeline_parser.add_argument('--denied-file', action='append', default=[])
    pipeline_parser.add_argument('--force-path', choices=['', 'fast', 'parallel', 'governed'], default='')
    pipeline_parser.add_argument('--max-iterations', type=int, default=1)
    pipeline_parser.add_argument('--dry-run', action='store_true')
    pipeline_parser.add_argument('--allow-actual', action='store_true')
    pipeline_parser.add_argument(
        '--sandbox', choices=['read-only', 'workspace-write', 'danger-full-access'], default='workspace-write'
    )
    pipeline_parser.add_argument('--codex-home', default='')
    pipeline_parser.add_argument('--backend', default='')
    pipeline_parser.add_argument('--timeout-seconds', type=int, default=360)
    pipeline_parser.add_argument('--max-retries', type=int, default=2)
    pipeline_parser.add_argument('--debug', action='store_true', help='Show full internal runtime output.')
    pipeline_parser.set_defaults(handler=pipeline)

    # -- plan-big (suppressed)
    plan_big_parser = sub.add_parser('plan-big', help=argparse.SUPPRESS)
    plan_big_parser.add_argument('input', nargs='*')
    plan_big_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    plan_big_parser.add_argument('--run-id', default='run-big-task')
    plan_big_parser.add_argument('--goal-id', default='')
    plan_big_parser.set_defaults(handler=plan_big)

    # -- decompose (suppressed)
    decompose_parser = sub.add_parser('decompose', help=argparse.SUPPRESS)
    decompose_parser.add_argument('input', nargs='*')
    decompose_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    decompose_parser.add_argument('--run-id', default='run-big-task')
    decompose_parser.add_argument('--goal-id', default='')
    decompose_parser.add_argument('--allow-leaf-actual', action='store_true')
    decompose_parser.set_defaults(handler=decompose_big)

    # -- aggregate (suppressed)
    aggregate_parser = sub.add_parser('aggregate', help=argparse.SUPPRESS)
    aggregate_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    aggregate_parser.add_argument('--run-id', required=True)
    aggregate_parser.add_argument('--goal-id', default='')
    aggregate_parser.add_argument('--max-iterations', type=int, default=10)
    aggregate_parser.set_defaults(handler=aggregate_big)

    # -- goal-loop (suppressed)
    goal_loop_parser = sub.add_parser('goal-loop', help=argparse.SUPPRESS)
    goal_loop_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    goal_loop_parser.add_argument('--run-id', required=True)
    goal_loop_parser.add_argument('--goal-id', default='')
    goal_loop_parser.add_argument('--max-iterations', type=int, default=10)
    goal_loop_parser.add_argument('--no-advance', action='store_true')
    goal_loop_parser.add_argument('--no-next-goal-suggestions', action='store_true')
    goal_loop_parser.set_defaults(handler=goal_loop)

    # -- global-loop (suppressed)
    global_loop_parser = sub.add_parser('global-loop', help=argparse.SUPPRESS)
    global_loop_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    global_loop_parser.add_argument('--max-iterations', type=int, default=100)
    global_loop_parser.add_argument('--max-continuous-goal-iterations', type=int, default=3)
    global_loop_parser.add_argument('--backend-health', default='')
    global_loop_parser.add_argument('--no-advance', action='store_true')
    global_loop_parser.set_defaults(handler=global_loop)

    # -- integration-check (suppressed)
    integration_parser = sub.add_parser('integration-check', help=argparse.SUPPRESS)
    integration_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    integration_parser.add_argument('--run-id', required=True)
    integration_parser.add_argument(
        '--yes', action='store_true', help='Actually create the isolated integration worktree.'
    )
    integration_parser.set_defaults(handler=integration_check)

    # -- start
    start_parser = sub.add_parser('start', help='Start map-backed project progress.')
    start_parser.add_argument('goal', nargs='*')
    start_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    start_parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='standard')
    start_parser.add_argument('--max-steps', type=int, default=0)
    start_parser.add_argument('--steps', type=int, default=0, help=argparse.SUPPRESS)
    start_parser.add_argument('--backend', default='')
    start_parser.add_argument('--debug', action='store_true')
    start_parser.set_defaults(handler=start_command)

    # -- continue
    continue_parser = sub.add_parser('continue', help='Continue the current project session.')
    continue_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    continue_parser.add_argument('--mode', choices=['preview', 'standard', 'autopilot'], default='standard')
    continue_parser.add_argument('--max-steps', type=int, default=0)
    continue_parser.add_argument('--steps', type=int, default=0, help=argparse.SUPPRESS)
    continue_parser.add_argument('--backend', default='')
    continue_parser.set_defaults(handler=continue_command)

    # -- stop
    stop_parser = sub.add_parser('stop', help='Stop the current project session.')
    stop_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    stop_parser.add_argument('--debug', action='store_true')
    stop_parser.set_defaults(handler=stop_command)

    # -- status
    status_parser = sub.add_parser('status', help='Show workspace runtime status.')
    status_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    status_parser.add_argument('--run-id', default='')
    status_parser.add_argument('--no-write', action='store_true')
    status_parser.add_argument('--debug', action='store_true')
    status_parser.set_defaults(handler=status)

    # -- cockpit
    cockpit_parser = sub.add_parser('cockpit', help='Generate a local Project Cockpit.')
    cockpit_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    cockpit_parser.add_argument('--dogfood', action='store_true', help=argparse.SUPPRESS)
    cockpit_parser.add_argument('--debug', action='store_true')
    cockpit_parser.set_defaults(handler=cockpit_command)

    # -- release
    release_parser = sub.add_parser('release', help='Generate a local release workflow pack.')
    release_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    release_parser.add_argument('--doctor', action='store_true', help=argparse.SUPPRESS)
    release_parser.add_argument('--safety-check', dest='safety_check', action='store_true', help=argparse.SUPPRESS)
    release_parser.add_argument('--dogfood', action='store_true', help=argparse.SUPPRESS)
    release_parser.add_argument('--debug', action='store_true')
    release_parser.set_defaults(handler=release_command)

    # -- pr
    pr_parser = sub.add_parser('pr', help='Generate a local PR draft.')
    pr_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    pr_parser.add_argument('--debug', action='store_true')
    pr_parser.set_defaults(handler=pr_command)

    # -- alpha (suppressed)
    alpha_parser = sub.add_parser('alpha', help=argparse.SUPPRESS)
    alpha_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    alpha_parser.add_argument('--audit', action='store_true')
    alpha_parser.add_argument('--package', action='store_true')
    alpha_parser.add_argument('--report', action='store_true')
    alpha_parser.add_argument('--debug', action='store_true')
    alpha_parser.set_defaults(handler=alpha_command)

    # -- publish (suppressed)
    publish_parser = sub.add_parser('publish', help=argparse.SUPPRESS)
    publish_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    publish_parser.add_argument('--preflight', action='store_true')
    publish_parser.add_argument('--package', action='store_true')
    publish_parser.add_argument('--report', action='store_true')
    publish_parser.add_argument('--debug', action='store_true')
    publish_parser.set_defaults(handler=publish_command)

    # -- launch (suppressed)
    launch_parser = sub.add_parser('launch', help=argparse.SUPPRESS)
    launch_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    launch_parser.add_argument('--package', action='store_true')
    launch_parser.add_argument('--audit', action='store_true')
    launch_parser.add_argument('--report', action='store_true')
    launch_parser.add_argument('--smoke', action='store_true')
    launch_parser.add_argument('--debug', action='store_true')
    launch_parser.set_defaults(handler=launch_command)

    # -- postlaunch (suppressed)
    postlaunch_parser = sub.add_parser('postlaunch', help=argparse.SUPPRESS)
    postlaunch_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    postlaunch_parser.add_argument('--verify', action='store_true')
    postlaunch_parser.add_argument('--branch-audit', dest='branch_audit', action='store_true')
    postlaunch_parser.add_argument('--report', action='store_true')
    postlaunch_parser.add_argument('--debug', action='store_true')
    postlaunch_parser.set_defaults(handler=postlaunch_command)

    # -- feedback (suppressed)
    feedback_parser = sub.add_parser('feedback', help=argparse.SUPPRESS)
    feedback_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    feedback_parser.add_argument('--triage', action='store_true')
    feedback_parser.add_argument('--report', action='store_true')
    feedback_parser.add_argument('--signals', action='store_true')
    feedback_parser.add_argument('--debug', action='store_true')
    feedback_parser.set_defaults(handler=feedback_command)

    # -- session (suppressed)
    session_parser = sub.add_parser('session', help=argparse.SUPPRESS)
    session_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    session_parser.add_argument('--dogfood', action='store_true')
    session_parser.add_argument('--debug', action='store_true')
    session_parser.set_defaults(handler=session_command)

    # -- workers (suppressed)
    workers_parser = sub.add_parser('workers', help=argparse.SUPPRESS)
    workers_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    workers_parser.add_argument('--doctor', action='store_true')
    workers_parser.add_argument('--list', action='store_true')
    workers_parser.add_argument('--route-demo', action='store_true')
    workers_parser.add_argument('--dogfood', action='store_true')
    workers_parser.add_argument('--real-dogfood', dest='real_dogfood', action='store_true')
    workers_parser.add_argument('--debug', action='store_true')
    workers_parser.set_defaults(handler=workers_command)

    # -- learning (suppressed)
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

    # -- undo (suppressed)
    undo_parser = sub.add_parser('undo', help=argparse.SUPPRESS)
    undo_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    undo_parser.add_argument('--preview', action='store_true')
    undo_parser.add_argument('--apply', action='store_true')
    undo_parser.add_argument('--yes', action='store_true', help='Confirm undo apply.')
    undo_parser.set_defaults(handler=undo_command)

    # -- rollback (suppressed)
    rollback_parser = sub.add_parser('rollback', help=argparse.SUPPRESS)
    rollback_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    rollback_parser.add_argument('--run-id', required=True)
    rollback_parser.add_argument('--task-id', required=True)
    rollback_parser.add_argument('--dry-run', action='store_true')
    rollback_parser.add_argument('--yes', action='store_true')
    rollback_parser.add_argument('--confirm-current-branch', action='store_true')
    rollback_parser.add_argument('--debug', action='store_true')
    rollback_parser.set_defaults(handler=rollback)

    # -- reroute (suppressed)
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

    # -- map (suppressed)
    map_parser = sub.add_parser('map', help=argparse.SUPPRESS)
    map_sub = map_parser.add_subparsers(dest='map_action', required=True)
    for action in ['check', 'refresh', 'promote']:
        item = map_sub.add_parser(action)
        item.add_argument('--workspace', '--project', dest='workspace', default='.')
        item.add_argument('--dry-run', action='store_true')
        item.add_argument('--promote-if-missing', action='store_true')
        item.set_defaults(handler=map_command)

    # -- standards (suppressed)
    standards_parser = sub.add_parser('standards', help=argparse.SUPPRESS)
    standards_sub = standards_parser.add_subparsers(dest='standards_action', required=True)
    for action in ['check', 'promote']:
        item = standards_sub.add_parser(action)
        item.add_argument('--workspace', '--project', dest='workspace', default='.')
        item.add_argument('--refresh', action='store_true')
        item.add_argument('--dry-run', action='store_true')
        item.set_defaults(handler=standards)

    # -- review (suppressed)
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

    # -- backend
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

    # -- config (suppressed)
    config_parser = sub.add_parser('config', help=argparse.SUPPRESS)
    config_sub = config_parser.add_subparsers(dest='config_action', required=True)
    config_backend = config_sub.add_parser('backend')
    config_backend.add_argument('name')
    config_backend.add_argument('--workspace', '--project', dest='workspace', default='.')
    config_backend.set_defaults(handler=config_command)

    # -- debug (suppressed)
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

    # -- goal
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

    # -- loop (suppressed)
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

    # -- codex-health (suppressed)
    health_parser = sub.add_parser('codex-health', help=argparse.SUPPRESS)
    health_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    health_parser.add_argument('--mode', choices=['quick', 'full'], default='full')
    health_parser.add_argument('--codex-home', default=os.environ.get('CODEX_HOME', ''))
    health_parser.add_argument('--timeout-seconds', type=int, default=240)
    health_parser.add_argument('--no-output-timeout-seconds', type=int, default=120)
    health_parser.add_argument('--skip-real-codex', action='store_true')
    health_parser.set_defaults(handler=codex_health)

    # -- stats
    stats_parser = sub.add_parser('stats', help='Show usage statistics and cost summary.')
    stats_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    stats_parser.add_argument('--record', action='store_true', help=argparse.SUPPRESS)
    stats_parser.add_argument('--record-worker', default='')
    stats_parser.add_argument('--record-duration', type=float, default=0.0)
    stats_parser.set_defaults(handler=stats_command)

    # -- audit
    audit_parser = sub.add_parser('audit', help='Query the audit log.')
    audit_parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    audit_parser.add_argument('--summary', action='store_true', help='Show daily summary.')
    audit_parser.add_argument('--limit', type=int, default=50)
    audit_parser.add_argument('--event-type', default='')
    audit_parser.add_argument('--worker', default='')
    audit_parser.add_argument('--log', action='store_true', help=argparse.SUPPRESS)
    audit_parser.add_argument('--log-event', default='')
    audit_parser.add_argument('--log-worker', default='')
    audit_parser.add_argument('--log-task', default='')
    audit_parser.set_defaults(handler=audit_command)

    args = parser.parse_args(raw_argv)
    if args.command in {'run', 'pipeline'} and not ' '.join(args.input).strip():
        print('Missing task input.', file=sys.stderr)
        return 2
    return args.handler(args)


if __name__ == '__main__':
    raise SystemExit(main())
