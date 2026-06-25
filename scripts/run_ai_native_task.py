#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from build_task_context import build_context, write_context
from execution_policy import DEFAULT_DENIED_FILES, ExecutionPolicyInput, safe_name, select_execution_path


def run_command(cmd, cwd: Path, *, timeout=None) -> dict:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=timeout,
        )
        return {
            'command': [str(x) for x in cmd],
            'cwd': str(cwd),
            'returncode': proc.returncode,
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'command': [str(x) for x in cmd],
            'cwd': str(cwd),
            'returncode': 124,
            'stdout': exc.stdout or '',
            'stderr': exc.stderr or '',
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': True,
        }


def git_root(workspace: Path) -> Path:
    proc = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        cwd=workspace,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or 'workspace is not a git repository')
    return Path(proc.stdout.strip()).resolve()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def task_args(args) -> list[str]:
    values = []
    for pattern in args.allowed_file:
        values += ['--allowed-file', pattern]
    for pattern in args.denied_file:
        values += ['--denied-file', pattern]
    for command in args.test_command:
        values += ['--test-command', command]
    return values


def run_optimistic(args) -> dict:
    cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'run_optimistic_worker.py'),
        '--run-id',
        args.run_id,
        '--task-id',
        args.task_id,
        '--workspace',
        args.workspace,
        '--objective',
        args.objective,
        '--sandbox',
        args.sandbox,
        '--timeout-seconds',
        str(args.timeout_seconds),
        '--no-output-timeout-seconds',
        str(args.no_output_timeout_seconds),
        '--test-timeout-seconds',
        str(args.test_timeout_seconds),
        '--max-retries',
        str(args.max_retries),
        '--start-point',
        args.start_point,
        *task_args(args),
    ]
    if args.worktree_root:
        cmd += ['--worktree-root', args.worktree_root]
    if args.profile:
        cmd += ['--profile', args.profile]
    if args.codex_home:
        cmd += ['--codex-home', args.codex_home]
    if getattr(args, 'goal_id', ''):
        cmd += ['--goal-id', args.goal_id]
    if args.allow_hard_risk:
        cmd += ['--allow-hard-risk']
    if args.full_prompt:
        cmd += ['--full-prompt']
    if args.discard_failed_worktree:
        cmd += ['--discard-failed-worktree']
    if args.ephemeral:
        cmd += ['--ephemeral']
    if args.dry_run:
        cmd += ['--dry-run']
    if getattr(args, 'task_context', ''):
        cmd += ['--task-context', args.task_context]
    return run_command(cmd, ROOT, timeout=args.timeout_seconds + 60 if args.timeout_seconds > 0 else None)


def run_planned_isolated(args) -> dict:
    cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'run_optimistic_worker.py'),
        '--run-id',
        args.run_id,
        '--task-id',
        args.task_id,
        '--workspace',
        args.workspace,
        '--objective',
        args.objective,
        '--sandbox',
        args.sandbox,
        '--timeout-seconds',
        str(args.timeout_seconds),
        '--no-output-timeout-seconds',
        str(args.no_output_timeout_seconds),
        '--test-timeout-seconds',
        str(args.test_timeout_seconds),
        '--max-retries',
        str(args.max_retries),
        '--start-point',
        args.start_point,
        '--full-prompt',
        '--allow-hard-risk',
        '--execution-path',
        'planned_worker',
        *task_args(args),
    ]
    if args.worktree_root:
        cmd += ['--worktree-root', args.worktree_root]
    if args.profile:
        cmd += ['--profile', args.profile]
    if args.codex_home:
        cmd += ['--codex-home', args.codex_home]
    if getattr(args, 'goal_id', ''):
        cmd += ['--goal-id', args.goal_id]
    if args.discard_failed_worktree:
        cmd += ['--discard-failed-worktree']
    if args.ephemeral:
        cmd += ['--ephemeral']
    if args.dry_run:
        cmd += ['--dry-run']
    if getattr(args, 'task_context', ''):
        cmd += ['--task-context', args.task_context]
    return run_command(cmd, ROOT, timeout=args.timeout_seconds + 60 if args.timeout_seconds > 0 else None)


def generate_planned_task_pack(args, repo_root: Path, path: str) -> dict:
    task_dir = repo_root / '.zoo-agent' / 'runs' / args.run_id / 'codex-tasks' / args.task_id
    prompt_template = 'CODEX_TASK_PROMPT.md'
    cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'generate_codex_task_pack.py'),
        '--run-id',
        args.run_id,
        '--task-id',
        args.task_id,
        '--objective',
        args.objective,
        '--goal-id',
        args.goal_id,
        '--worktree',
        args.workspace,
        '--output',
        str(task_dir),
        '--prompt-template',
        prompt_template,
        *task_args(args),
    ]
    if getattr(args, 'task_context', ''):
        cmd += ['--task-context', args.task_context]
    result = run_command(cmd, repo_root)
    result['task_dir'] = str(task_dir)
    result['planned_path'] = path
    return result


def is_test_pattern(pattern: str) -> bool:
    normalized = pattern.replace('\\', '/').lower()
    parts = [p.strip('*').lower() for p in normalized.split('/') if p]
    return (
        any(part in {'test', 'tests', 'spec', 'specs'} for part in parts)
        or 'test' in normalized
        or 'spec' in normalized
    )


def surface_key(pattern: str) -> str:
    normalized = pattern.replace('\\', '/').strip('/')
    parts = [p for p in normalized.split('/') if p and '*' not in p]
    if not parts:
        return 'general'
    if parts[0].lower() in {'src', 'app', 'lib', 'packages', 'services'} and len(parts) > 1:
        return parts[1].lower()
    return parts[0].lower()


def matching_tests(prod_pattern: str, test_patterns: list[str]) -> list[str]:
    if not test_patterns:
        return []
    key = surface_key(prod_pattern)
    matched = [pattern for pattern in test_patterns if key != 'general' and key in pattern.replace('\\', '/').lower()]
    return matched or test_patterns


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_leaf_command(args, leaf: dict) -> list[str]:
    cmd = [
        'python',
        '.\\scripts\\run_ai_native_task.py',
        '--run-id',
        args.run_id,
        '--task-id',
        leaf['task_id'],
        '--workspace',
        args.workspace,
        '--objective',
        leaf['objective'],
        '--governance-level',
        str(leaf['recommended_governance_level']),
    ]
    if getattr(args, 'goal_id', ''):
        cmd += ['--goal-id', args.goal_id]
    for pattern in leaf['allowed_files']:
        cmd += ['--allowed-file', pattern]
    for pattern in leaf['denied_files']:
        cmd += ['--denied-file', pattern]
    for command in leaf['test_commands']:
        cmd += ['--test-command', command]
    return cmd


def build_leaf_skeletons(args) -> list[dict]:
    allowed = [pattern for pattern in args.allowed_file if pattern]
    denied = [pattern for pattern in args.denied_file if pattern]
    tests = [command for command in args.test_command if command]
    test_patterns = [pattern for pattern in allowed if is_test_pattern(pattern)]
    prod_patterns = [pattern for pattern in allowed if not is_test_pattern(pattern)]
    if not prod_patterns:
        prod_patterns = allowed or ['**']

    leaves = []
    for index, pattern in enumerate(prod_patterns, start=1):
        leaf_allowed = [pattern, *matching_tests(pattern, test_patterns)]
        # Preserve order while removing duplicates.
        seen = set()
        leaf_allowed = [item for item in leaf_allowed if not (item in seen or seen.add(item))]
        leaf_task_id = f'{args.task_id}-leaf-{index:03d}'
        leaf_objective = f'Bounded leaf for `{pattern}` under parent objective: {args.objective}'
        leaf_selection = select_execution_path(
            ExecutionPolicyInput(
                run_id=args.run_id,
                task_id=leaf_task_id,
                objective=leaf_objective,
                allowed_files=leaf_allowed,
                denied_files=denied,
                test_commands=tests,
                changed_file_estimate=0,
                governance_level=1,
            )
        )
        leaf_graph = leaf_selection.get('execution_graph') or {}
        parallel_contract = leaf_graph.get('parallel_contract') or {}
        leaf = {
            'parent_task_id': args.task_id,
            'task_id': leaf_task_id,
            'status': 'draft',
            'recommended_governance_level': 1,
            'recommended_execution_path': leaf_selection.get('recommended_path', 'optimistic_worker'),
            'objective': leaf_objective,
            'allowed_files': leaf_allowed,
            'denied_files': denied,
            'test_commands': tests,
            'execution_graph': leaf_graph,
            'parallelizable': bool(parallel_contract.get('parallelizable')),
            'parallel_group': f'{safe_name(args.run_id)}/{safe_name(args.task_id)}/leaf-candidates',
            'conflict_keys': parallel_contract.get('conflict_keys') or [],
            'rollback_mode': (leaf_graph.get('rollback_contract') or {}).get('mode', 'discard_isolated_worktree'),
            'notes': [
                'Refine the objective before execution if this leaf is still too broad.',
                'Run this leaf through the dispatcher; do not inherit the parent Level 3 weight.',
                'The dispatcher will re-check hard-risk rules before executing.',
                'Leaves can run in parallel only when their conflict_keys do not overlap.',
            ],
        }
        leaf['dispatcher_command'] = build_leaf_command(args, leaf)
        leaf['powershell_command'] = ' '.join(
            shell_quote(part) if any(ch.isspace() for ch in part) else part for part in leaf['dispatcher_command']
        )
        leaves.append(leaf)
    return leaves


def materialize_leaf_skeletons(args, workstream_dir: Path, leaves: list[dict]) -> dict:
    leaf_dir = workstream_dir / safe_name(args.task_id) / 'leaf-tasks'
    leaf_dir.mkdir(parents=True, exist_ok=True)
    leaf_index = []
    for leaf in leaves:
        leaf_path = leaf_dir / f'{safe_name(leaf["task_id"])}.json'
        md_path = leaf_path.with_suffix('.md')
        leaf_path.write_text(json.dumps(leaf, ensure_ascii=False, indent=2), encoding='utf-8')
        md_path.write_text(
            '\n'.join(
                [
                    f'# Leaf Task: {leaf["task_id"]}',
                    '',
                    f'Status: {leaf["status"]}',
                    '',
                    '## Objective',
                    '',
                    leaf['objective'],
                    '',
                    '## Default Dispatcher Command',
                    '',
                    '```powershell',
                    leaf['powershell_command'],
                    '```',
                    '',
                    '## Execution Graph',
                    '',
                    f'- recommended_execution_path: {leaf.get("recommended_execution_path")}',
                    f'- chain_weight: {(leaf.get("execution_graph") or {}).get("chain_weight", "unknown")}',
                    f'- misroute_risk: {(leaf.get("execution_graph") or {}).get("misroute_risk", "unknown")}',
                    f'- parallelizable: {leaf.get("parallelizable")}',
                    f'- conflict_keys: {json.dumps(leaf.get("conflict_keys") or [], ensure_ascii=False)}',
                    f'- rollback_mode: {leaf.get("rollback_mode")}',
                    '',
                ]
            ),
            encoding='utf-8',
        )
        leaf_index.append(
            {
                'task_id': leaf['task_id'],
                'json': str(leaf_path),
                'markdown': str(md_path),
                'recommended_execution_path': leaf.get('recommended_execution_path'),
                'parallelizable': leaf.get('parallelizable'),
                'parallel_group': leaf.get('parallel_group'),
                'conflict_keys': leaf.get('conflict_keys') or [],
                'rollback_mode': leaf.get('rollback_mode'),
            }
        )
    index_path = leaf_dir / 'leaf-tasks.json'
    index_payload = {
        'parent_task_id': args.task_id,
        'status': 'draft',
        'leaf_count': len(leaf_index),
        'leaves': leaf_index,
    }
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'directory': str(leaf_dir), 'index': str(index_path), 'leaf_count': len(leaf_index), 'leaves': leaf_index}


def write_fractal_workstream(args, repo_root: Path, selection: dict, task_pack: dict) -> dict:
    workstream_dir = repo_root / '.zoo-agent' / 'runs' / args.run_id / 'fractal-workstreams'
    workstream_path = workstream_dir / f'{safe_name(args.task_id)}.json'
    md_path = workstream_path.with_suffix('.md')
    leaves = build_leaf_skeletons(args)
    leaf_artifacts = materialize_leaf_skeletons(args, workstream_dir, leaves)
    payload = {
        'run_id': args.run_id,
        'task_id': args.task_id,
        'status': 'leaf_skeletons_ready',
        'objective': args.objective,
        'selection': selection,
        'parent_task_pack': task_pack.get('task_dir', ''),
        'leaf_skeletons': leaf_artifacts,
        'leaf_execution_contract': {
            'runner': 'run_ai_native_task.py',
            'required_leaf_fields': [
                'task_id',
                'objective',
                'allowed_files',
                'test_commands',
                'execution_graph',
                'conflict_keys',
            ],
            'recommended_governance_level': 1,
            'parallelization_policy': 'leaf tasks may run concurrently only when conflict_keys do not overlap',
            'rollback_policy': 'failed leaf worktrees may be discarded without changing the parent workstream',
            'notes': [
                'Create one bounded leaf per independently verifiable change.',
                'Run each leaf in its own managed worktree.',
                'Aggregate merge candidates only after each leaf passes scope guard and tests.',
            ],
        },
    }
    workstream_path.parent.mkdir(parents=True, exist_ok=True)
    workstream_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text(
        '\n'.join(
            [
                f'# Fractal Workstream: {args.task_id}',
                '',
                f'Status: {payload["status"]}',
                '',
                '## Objective',
                '',
                args.objective,
                '',
                '## Next Step',
                '',
                'Review the generated leaf skeletons, refine any broad leaf, then run each leaf through `run_ai_native_task.py`.',
                '',
                '## Leaf Skeletons',
                '',
                *[f'- {leaf["task_id"]}: {leaf["json"]}' for leaf in leaf_artifacts['leaves']],
                '',
            ]
        ),
        encoding='utf-8',
    )
    return {
        'json': str(workstream_path),
        'markdown': str(md_path),
        'status': payload['status'],
        'leaf_skeletons': leaf_artifacts,
    }


def refresh_summary(run_id: str, repo_root: Path) -> dict:
    cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'summarize_ai_native_run.py'),
        '--run-id',
        run_id,
        '--workspace',
        str(repo_root),
    ]
    return run_command(cmd, ROOT)


def finish(report_path: Path, report: dict, args, repo_root: Path, returncode: int) -> int:
    write_json(report_path, report)
    summary = refresh_summary(args.run_id, repo_root)
    if summary.get('returncode') != 0:
        report['summary_refresh'] = summary
        write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return returncode


def main() -> int:
    ap = argparse.ArgumentParser(description='Zoo AI-native task dispatcher: route, execute, verify, and report.')
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--objective', required=True)
    ap.add_argument('--allowed-file', action='append', default=[])
    ap.add_argument('--denied-file', action='append', default=DEFAULT_DENIED_FILES)
    ap.add_argument('--test-command', action='append', default=[])
    ap.add_argument('--changed-file-estimate', type=int, default=0)
    ap.add_argument('--goal-id', default='')
    ap.add_argument('--allow-durable-state-update', action='store_true')
    ap.add_argument(
        '--force-path',
        default='',
        choices=['', 'optimistic_worker', 'planned_worker', 'fractal_governed', 'human_gate'],
    )
    ap.add_argument('--governance-level', type=int, choices=[0, 1, 2, 3, 4], default=None)
    ap.add_argument('--worktree-root', default='')
    ap.add_argument('--start-point', default='HEAD')
    ap.add_argument(
        '--sandbox', default='workspace-write', choices=['read-only', 'workspace-write', 'danger-full-access']
    )
    ap.add_argument('--profile', default='')
    ap.add_argument('--codex-home', default='')
    ap.add_argument('--timeout-seconds', type=int, default=360)
    ap.add_argument('--no-output-timeout-seconds', type=int, default=600)
    ap.add_argument('--test-timeout-seconds', type=int, default=0)
    ap.add_argument('--max-retries', type=int, default=1)
    ap.add_argument('--allow-hard-risk', action='store_true')
    ap.add_argument('--full-prompt', action='store_true')
    ap.add_argument('--discard-failed-worktree', action='store_true')
    ap.add_argument('--ephemeral', action='store_true')
    ap.add_argument(
        '--skip-health-check',
        action='store_true',
        help='Accepted for route_task compatibility; health is checked before dispatch.',
    )
    ap.add_argument(
        '--execute-planned', action='store_true', help='Run planned worker immediately after task pack generation'
    )
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if not args.allowed_file:
        print('At least one --allowed-file is required.', file=sys.stderr)
        return 2

    workspace = Path(args.workspace).resolve()
    if not workspace.exists():
        print(f'Missing workspace: {workspace}', file=sys.stderr)
        return 2
    repo_root = git_root(workspace)
    run_dir = repo_root / '.zoo-agent' / 'runs' / args.run_id
    selection_path = run_dir / 'executor-selection.json'
    dispatcher_report_path = run_dir / 'dispatcher-runs' / f'{safe_name(args.task_id)}.json'
    task_context = build_context(
        repo_root, args.run_id, args.task_id, args.objective, args.goal_id, args.allow_durable_state_update
    )
    task_context_paths = write_context(repo_root, args.run_id, args.task_id, task_context)
    args.task_context = task_context_paths['json']

    selection = select_execution_path(
        ExecutionPolicyInput(
            run_id=args.run_id,
            task_id=args.task_id,
            objective=args.objective,
            allowed_files=args.allowed_file,
            denied_files=args.denied_file,
            test_commands=args.test_command,
            changed_file_estimate=args.changed_file_estimate,
            force_path=args.force_path,
            governance_level=args.governance_level,
        )
    )
    selection['selected_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
    selection['task_context'] = task_context_paths
    write_json(selection_path, selection)

    if args.dry_run:
        report = {
            'status': 'dry_run',
            'selection': selection,
            'task_context': task_context_paths,
            'recommended_next_action': 'run without --dry-run',
        }
        return finish(dispatcher_report_path, report, args, repo_root, 0)

    path = selection['recommended_path']
    if path == 'optimistic_worker':
        execution = run_optimistic(args)
        status = 'optimistic_executed' if execution.get('returncode') == 0 else 'optimistic_failed_or_escalated'
        report = {
            'status': status,
            'selection': selection,
            'task_context': task_context_paths,
            'execution': execution,
            'recommended_next_action': 'inspect optimistic run report and merge candidate'
            if execution.get('returncode') == 0
            else 'inspect failure policy and escalate if needed',
        }
        return finish(dispatcher_report_path, report, args, repo_root, execution.get('returncode', 10))

    if path in {'planned_worker', 'fractal_governed'}:
        if args.execute_planned and path == 'planned_worker':
            execution = run_planned_isolated(args)
            report = {
                'status': 'planned_executed_isolated'
                if execution.get('returncode') == 0
                else 'planned_execution_failed_or_escalated',
                'selection': selection,
                'task_context': task_context_paths,
                'execution': execution,
                'recommended_next_action': 'inspect planned isolated run report and merge candidate'
                if execution.get('returncode') == 0
                else 'inspect failure policy and escalate if needed',
            }
            return finish(dispatcher_report_path, report, args, repo_root, execution.get('returncode', 10))

        pack = generate_planned_task_pack(args, repo_root, path)
        report = {
            'status': 'planned_pack_ready' if pack.get('returncode') == 0 else 'planned_pack_failed',
            'selection': selection,
            'task_context': task_context_paths,
            'task_pack': pack,
            'recommended_next_action': 'review plan/scope, then run run_codex_worker.py or decompose leaf tasks',
        }
        if path == 'fractal_governed' and pack.get('returncode') == 0:
            report['fractal_workstream'] = write_fractal_workstream(args, repo_root, selection, pack)
            report['status'] = 'fractal_workstream_ready'
            report['recommended_next_action'] = (
                'review generated leaf skeletons, refine broad leaves, then run each leaf through run_ai_native_task.py'
            )
        return finish(
            dispatcher_report_path,
            report,
            args,
            repo_root,
            0 if report['status'] in {'planned_pack_ready', 'planned_executed', 'fractal_workstream_ready'} else 10,
        )

    report = {
        'status': 'human_gate_required',
        'selection': selection,
        'task_context': task_context_paths,
        'recommended_next_action': 'manual approval required before execution',
    }
    return finish(dispatcher_report_path, report, args, repo_root, 20)


if __name__ == '__main__':
    raise SystemExit(main())
