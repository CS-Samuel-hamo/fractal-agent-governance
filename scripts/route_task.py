#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from execution_policy import DEFAULT_DENIED_FILES  # noqa: E402
from runtime_common import (  # noqa: E402
    advance_loop,
    alignment_report,
    ensure_goal,
    load_json,
    project_root,
    safe_name,
    utc_now,
    write_json,
)
from check_task_specificity import evaluate as evaluate_specificity  # noqa: E402
from task_classifier import classify  # noqa: E402
from update_runtime_metrics import update_metrics  # noqa: E402

FAST_SKIPPED_GOVERNANCE = [
    'product_doc_generation',
    'full_planning_loop',
    'fractal_decomposition',
    'implementation_queue',
    'governed_reviewer',
    'curator_lesson_extraction',
    'eval_suite',
    'parent_aggregation',
    'merge_queue',
]

LOCAL_OPTIMIZATION_TERMS = ['optimize', 'optimization', 'cleanup', 'polish', 'tune', 'refactor', 'local', '\u4f18\u5316', '\u6574\u7406']
CODING_INTENT_TERMS = ['implement', 'code', 'build', 'validation', 'bug', 'form', 'api', 'schema', 'database', '\u5b9e\u73b0', '\u4fee\u590d', '\u65b0\u589e']
DOC_INTENT_TERMS = ['readme', 'doc', 'docs', 'documentation', 'typo', 'markdown', '\u6587\u6863']
HEALTHY_CODEX_WORKER_VERDICTS = {'HEALTHY', 'HEALTHY_WITH_WARNINGS'}


def run_command(command: list[str], cwd: Path, *, timeout: int = 0) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout or None,
        )
        return {
            'command': [str(part) for part in command],
            'cwd': str(cwd),
            'returncode': proc.returncode,
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'command': [str(part) for part in command],
            'cwd': str(cwd),
            'returncode': 124,
            'stdout': exc.stdout or '',
            'stderr': exc.stderr or '',
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': True,
        }


def task_id_default(text: str) -> str:
    return f'task-{safe_name(text[:40]).lower()}'


def add_repeated_args(command: list[str], flag: str, values: list[str]) -> None:
    for value in values:
        command.extend([flag, str(value)])


def latest_codex_health_report() -> dict[str, Any]:
    candidates: list[Path] = []
    latest = ROOT / '.tmp' / 'codex-worker-health-latest.json'
    if latest.exists():
        candidates.append(latest)
    candidates.extend(sorted((ROOT / '.tmp').glob('codex-worker-health-*.json'), reverse=True))
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        payload = load_json(resolved)
        if payload:
            payload['_path'] = str(resolved)
            return payload
    return {}


def codex_health_ok(max_age_hours: int = 24) -> tuple[bool, dict[str, Any]]:
    payload = latest_codex_health_report()
    if not payload:
        return False, {'verdict': 'missing', 'message': 'No Codex worker health report found.'}
    verdict = str(payload.get('verdict') or payload.get('health_verdict') or '')
    generated_at = str(payload.get('generated_at') or payload.get('created_at') or '')
    stale = False
    if generated_at:
        try:
            created = datetime.datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
            if created.tzinfo is None:
                created = created.replace(tzinfo=datetime.timezone.utc)
            age = datetime.datetime.now(datetime.timezone.utc) - created.astimezone(datetime.timezone.utc)
            stale = age.total_seconds() > max_age_hours * 3600
        except ValueError:
            stale = False
    if stale:
        payload['_health_stale'] = True
    return verdict in HEALTHY_CODEX_WORKER_VERDICTS and not stale, payload


def has_local_optimization_intent(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in LOCAL_OPTIMIZATION_TERMS)


def is_doc_only_coding_task(text: str, allowed_files: list[str]) -> bool:
    lowered = text.lower()
    has_coding_intent = any(term in lowered for term in CODING_INTENT_TERMS)
    doc_intent = any(term in lowered for term in DOC_INTENT_TERMS)
    if not has_coding_intent and not doc_intent and any(term in lowered for term in ['fix', 'add', 'change']):
        has_coding_intent = True
    if not has_coding_intent or not allowed_files:
        return False
    normalized = [str(item).replace('\\', '/').lower() for item in allowed_files]
    return all(item.startswith('docs/') or item.startswith('doc/') or item.endswith('.md') or item in {'docs/**', '*.md'} for item in normalized)


def fast_statuses(execution: dict[str, Any]) -> tuple[str, str]:
    if execution.get('status') == 'dry_run':
        return 'not_run_dry_run', 'not_run_dry_run'
    if execution.get('timed_out'):
        return 'unknown_timeout', 'unknown_timeout'
    returncode = execution.get('returncode')
    if returncode == 0:
        return 'passed_or_not_reported', 'passed_or_not_reported'
    if returncode is None:
        return 'unknown', 'unknown'
    return 'failed_or_not_reported', 'failed_or_not_reported'


def dispatcher_base(args, project: Path, goal_id: str, path: str) -> list[str]:
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'run_ai_native_task.py'),
        '--run-id',
        args.run_id,
        '--task-id',
        args.task_id,
        '--workspace',
        str(project),
        '--objective',
        args.input_text,
        '--goal-id',
        goal_id,
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
    ]
    if path == 'fast':
        command.extend(['--force-path', 'optimistic_worker'])
    elif path == 'governed':
        command.extend(['--governance-level', '3'])
    if args.codex_home:
        command.extend(['--codex-home', args.codex_home])
    if args.profile:
        command.extend(['--profile', args.profile])
    if args.discard_failed_worktree:
        command.append('--discard-failed-worktree')
    if args.ephemeral:
        command.append('--ephemeral')
    if args.dry_run or args.worker_dry_run:
        command.append('--dry-run')
    if args.skip_health_check:
        command.append('--skip-health-check')
    add_repeated_args(command, '--allowed-file', args.allowed_file)
    add_repeated_args(command, '--denied-file', args.denied_file)
    add_repeated_args(command, '--test-command', args.test_command)
    return command


def write_parallel_leaf_index(project: Path, args, classification: dict[str, Any]) -> dict[str, Any]:
    leaf_dir = project / '.zoo-agent' / 'runs' / args.run_id / 'cli-parallel' / safe_name(args.task_id) / 'leaf-tasks'
    leaves = []
    index_rows = []
    for index, task in enumerate(classification.get('tasks') or [], start=1):
        leaf_task_id = f'{args.task_id}-leaf-{index:03d}'
        allowed = [str(item) for item in task.get('allowed_files') or []]
        conflict_keys = [str(item) for item in task.get('conflict_keys') or []]
        leaf = {
            'schema_version': '1.0',
            'generated_by': 'route_task.py',
            'parent_task_id': args.task_id,
            'task_id': leaf_task_id,
            'status': 'ready',
            'recommended_governance_level': 1,
            'recommended_execution_path': 'optimistic_worker',
            'objective': task.get('objective') or args.input_text,
            'allowed_files': allowed,
            'denied_files': args.denied_file,
            'test_commands': args.test_command,
            'parallelizable': True,
            'conflict_keys': conflict_keys,
            'parallel_group': f'{safe_name(args.run_id)}/{safe_name(args.task_id)}/cli-parallel',
            'rollback_mode': 'discard_isolated_worktree',
            'execution_graph': {
                'schema_version': '1.0',
                'chain': 'optimistic_worker',
                'chain_weight': 'light',
                'parallel_contract': {
                    'parallelizable': True,
                    'conflict_keys': conflict_keys,
                    'conflict_rule': 'no overlapping conflict keys',
                },
                'rollback_contract': {
                    'mode': 'discard_isolated_worktree',
                    'automatic_discard_supported': True,
                },
            },
        }
        leaf_path = leaf_dir / f'{safe_name(leaf_task_id)}.json'
        write_json(leaf_path, leaf)
        leaves.append(leaf)
        index_rows.append(
            {
                'task_id': leaf_task_id,
                'json': str(leaf_path),
                'recommended_execution_path': 'optimistic_worker',
                'parallelizable': True,
                'conflict_keys': conflict_keys,
                'rollback_mode': 'discard_isolated_worktree',
            }
        )
    index_payload = {
        'schema_version': '1.0',
        'generated_by': 'route_task.py',
        'generated_at': utc_now(),
        'parent_task_id': args.task_id,
        'status': 'ready',
        'leaf_count': len(index_rows),
        'leaves': index_rows,
    }
    index_path = leaf_dir / 'leaf-tasks.json'
    write_json(index_path, index_payload)
    return {'index': str(index_path), 'directory': str(leaf_dir), 'leaf_count': len(index_rows), 'leaves': leaves}


def execute_parallel(project: Path, args, leaf_index: str, goal_id: str) -> dict[str, Any]:
    check_command = [
        sys.executable,
        str(ROOT / 'scripts' / 'check_codex_worker_concurrency.py'),
        '--workspace',
        str(project),
        '--run-id',
        args.run_id,
        '--leaf-index',
        leaf_index,
        '--max-workers',
        str(args.max_workers),
    ]
    check = run_command(check_command, ROOT)
    if check.get('returncode') != 0:
        return {'status': 'blocked_by_concurrency_check', 'concurrency_check': check}

    run_command_args = [
        sys.executable,
        str(ROOT / 'scripts' / 'run_codex_parallel_workers.py'),
        '--workspace',
        str(project),
        '--run-id',
        args.run_id,
        '--leaf-index',
        leaf_index,
        '--max-workers',
        str(args.max_workers),
        '--goal-id',
        goal_id,
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
    ]
    if args.codex_home:
        run_command_args.extend(['--codex-home', args.codex_home])
    if args.profile:
        run_command_args.extend(['--profile', args.profile])
    if args.worker_dry_run:
        run_command_args.append('--worker-dry-run')
    if args.discard_failed_worktree:
        run_command_args.append('--discard-failed-worktree')
    if args.ephemeral:
        run_command_args.append('--ephemeral')
    run = run_command(run_command_args, ROOT, timeout=args.timeout_seconds + 120 if args.timeout_seconds > 0 else 0)
    return {'status': 'parallel_executed' if run.get('returncode') == 0 else 'parallel_failed', 'concurrency_check': check, 'execution': run}


def write_runtime_marker(project: Path) -> None:
    marker = {
        'schema_version': '4.0',
        'generated_by': 'route_task.py',
        'updated_at': utc_now(),
        'runtime_model': {
            'cli_runtime': 'task routing, goal, loop, execution control',
            'codex_cli': 'execution backend',
            'gpt': 'decision layer',
            'deepseek': 'cheap analysis worker',
            'zoo_code': 'optional visualization and control UI',
        },
        'entrypoint_rule': 'CLI is the primary runtime entrypoint.',
    }
    write_json(project / '.zoo-agent' / 'runtime-v4.json', marker)


def run_fast_post_checks(project: Path, args) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    delivery_command = [
        sys.executable,
        str(ROOT / 'scripts' / 'check_delivery_outcome.py'),
        '--workspace',
        str(project),
        '--run-id',
        args.run_id,
        '--task-id',
        args.task_id,
    ]
    delivery_run = run_command(delivery_command, ROOT)
    gate_command = [
        sys.executable,
        str(ROOT / 'scripts' / 'check_fast_path_gate.py'),
        '--workspace',
        str(project),
        '--run-id',
        args.run_id,
        '--task-id',
        args.task_id,
    ]
    gate_run = run_command(gate_command, ROOT)
    run_dir = project / '.zoo-agent' / 'runs' / args.run_id
    return (
        load_json(run_dir / 'delivery-outcome.json'),
        load_json(run_dir / 'fast-path-gate.json'),
        delivery_run,
        gate_run,
    )


def route_and_execute(args) -> tuple[int, dict[str, Any]]:
    wall_started = time.monotonic()
    project = project_root(args.workspace)
    write_runtime_marker(project)
    args.task_id = args.task_id or task_id_default(args.input_text)
    goal = ensure_goal(project, goal_id=args.goal_id, run_id=args.run_id, fallback_goal=args.input_text)
    goal_id = str(goal.get('goal_id') or args.goal_id)
    loop_state = advance_loop(project, run_id=args.run_id, task_id=args.task_id, max_iteration=args.max_iteration)
    forced_path = 'fast' if args.fast else ('parallel' if args.parallel else ('governed' if args.governed else ''))
    classification = classify(
        project,
        args.input_text,
        allowed_files=args.allowed_file,
        denied_files=args.denied_file,
        changed_file_estimate=args.changed_file_estimate,
        force_path=forced_path,
    )
    args.allowed_file = [str(item) for item in classification.get('allowed_files') or args.allowed_file]
    alignment = alignment_report(project, objective=args.input_text, task_id=args.task_id, run_id=args.run_id, goal_id=goal_id, source='route_task.py')
    write_json(project / '.zoo-agent' / 'runs' / args.run_id / 'goal-alignment' / f'{safe_name(args.task_id)}.json', alignment)

    selected_path = classification['path']
    local_optimization_deferred = False
    if loop_state.get('status') == 'diverging' and has_local_optimization_intent(args.input_text):
        local_optimization_deferred = True
        classification['local_optimization_deferred'] = True
        classification['follow_up_reason'] = 'loop_convergence_force_follow_up'

    if loop_state.get('status') == 'diverging' and selected_path != 'governed':
        selected_path = 'governed'
        classification['path'] = 'governed'
        classification['reason'] = 'loop_diverging_escalate_to_gpt_decision_layer'
    if alignment.get('status') == 'blocked':
        selected_path = 'governed'
        classification['path'] = 'governed'
        classification['reason'] = 'goal_alignment_blocked_requires_gpt_decision_layer'

    run_dir = project / '.zoo-agent' / 'runs' / args.run_id
    report_path = run_dir / 'cli-runtime' / f'{safe_name(args.task_id)}.json'
    execution: dict[str, Any] = {'status': 'not_started'}
    task_specificity: dict[str, Any] = {}
    returncode = 0
    pre_codex_overhead_ms = 0.0
    codex_execution_ms = 0.0
    total_wall_time_ms = 0.0
    scope_guard_status = 'not_applicable'
    tests_status = 'not_applicable'

    if selected_path == 'fast':
        task_specificity = evaluate_specificity(args.input_text, args.allowed_file, route='fast')
        write_json(run_dir / 'task-specificity' / f'{safe_name(args.task_id)}.json', task_specificity)

    fast_needs_clarification = (
        selected_path == 'fast'
        and task_specificity.get('status') != 'pass'
        and not args.allow_ambiguous_fast
    )
    if fast_needs_clarification:
        pre_codex_overhead_ms = round((time.monotonic() - wall_started) * 1000, 3)
        execution = {
            'status': 'NEEDS_CLARIFICATION' if args.dry_run else 'no_execution',
            'message': 'Fast path task is too ambiguous for actual execution.',
            'task_specificity': task_specificity,
            'codex_launched': False,
            'recommended_next_action': 'clarify_task_or_pass_--allow-ambiguous-fast',
        }
        scope_guard_status = 'not_run'
        tests_status = 'not_run'
        returncode = 0 if args.dry_run else 10
    elif args.dry_run:
        execution = {'status': 'dry_run', 'message': 'No Codex backend command was launched.'}
        if selected_path == 'fast':
            pre_codex_overhead_ms = round((time.monotonic() - wall_started) * 1000, 3)
            scope_guard_status, tests_status = fast_statuses(execution)
    elif selected_path == 'fast':
        pre_codex_overhead_ms = round((time.monotonic() - wall_started) * 1000, 3)
        health_ok, health_report = (True, {'verdict': 'skipped_for_worker_dry_run'}) if args.worker_dry_run else codex_health_ok()
        if not health_ok and not args.skip_health_check:
            execution = {
                'status': 'blocked_codex_health_check_required',
                'message': 'Codex worker health check is missing, stale, or unhealthy. Run agent codex-health before actual fast execution.',
                'codex_launched': False,
                'health_report': health_report,
                'recommended_next_action': 'agent codex-health',
            }
            scope_guard_status = 'not_run'
            tests_status = 'not_run'
            returncode = 21
        else:
            command = dispatcher_base(args, project, goal_id, 'fast')
            execution = run_command(command, ROOT, timeout=args.timeout_seconds + 120 if args.timeout_seconds > 0 else 0)
            codex_execution_ms = round(float(execution.get('elapsed_seconds') or 0.0) * 1000, 3)
            scope_guard_status, tests_status = fast_statuses(execution)
            returncode = int(execution.get('returncode') or 0)
    elif selected_path == 'parallel':
        if not classification.get('independent'):
            execution = {
                'status': 'blocked_not_independent',
                'message': 'Parallel execution requires independent tasks with disjoint conflict keys and known isolated resources.',
                'parallel_denial_reason': classification.get('parallel_denial_reason') or 'not_independent',
            }
            returncode = 20
        else:
            leaf_index = write_parallel_leaf_index(project, args, classification)
            execution = execute_parallel(project, args, leaf_index['index'], goal_id)
            execution['leaf_index'] = leaf_index
            returncode = 0 if execution.get('status') == 'parallel_executed' else 10
    else:
        command = dispatcher_base(args, project, goal_id, 'governed')
        parent = run_command(command, ROOT, timeout=args.timeout_seconds + 120 if args.timeout_seconds > 0 else 0)
        implementation_queue = {
            'schema_version': '1.0',
            'generated_by': 'route_task.py',
            'generated_at': utc_now(),
            'run_id': args.run_id,
            'parent_task_id': args.task_id,
            'status': 'parent_decomposition_recorded',
            'parent_dispatcher': parent,
            'decision_layer': 'gpt_review_required',
            'worker_backend': 'codex_cli',
        }
        write_json(run_dir / 'implementation-queue.json', implementation_queue)
        execution = {'status': 'governed_parent_recorded', 'parent_dispatcher': parent, 'implementation_queue': implementation_queue}
        returncode = int(parent.get('returncode') or 0)
        leaf_index_path = run_dir / 'fractal-workstreams' / safe_name(args.task_id) / 'leaf-tasks' / 'leaf-tasks.json'
        if parent.get('returncode') == 0 and leaf_index_path.exists() and args.execute_governed_workers:
            worker_result = execute_parallel(project, args, str(leaf_index_path), goal_id)
            execution['worker_execution'] = worker_result
            returncode = 0 if worker_result.get('status') == 'parallel_executed' else 10
        gpt_review = {
            'schema_version': '1.0',
            'generated_by': 'route_task.py',
            'generated_at': utc_now(),
            'run_id': args.run_id,
            'task_id': args.task_id,
            'status': 'required',
            'decision_layer': 'GPT',
            'review_inputs': [
                str(report_path),
                str(run_dir / 'implementation-queue.json'),
                str(run_dir / 'parent-aggregation.json'),
                str(run_dir / 'merge-queue.json'),
            ],
        }
        write_json(run_dir / 'gpt-review.json', gpt_review)
        execution['gpt_review'] = gpt_review

    elapsed = 0.0
    if isinstance(execution.get('elapsed_seconds'), (int, float)):
        elapsed = float(execution.get('elapsed_seconds') or 0.0)
    elif isinstance(execution.get('execution'), dict):
        elapsed = float(execution['execution'].get('elapsed_seconds') or 0.0)
    elif isinstance(execution.get('parent_dispatcher'), dict):
        elapsed = float(execution['parent_dispatcher'].get('elapsed_seconds') or 0.0)
    if selected_path == 'fast' and not codex_execution_ms and elapsed:
        codex_execution_ms = round(elapsed * 1000, 3)
    total_wall_time_ms = round((time.monotonic() - wall_started) * 1000, 3)

    status_text = str(execution.get('status') or '')
    code_delivered = 'merge_candidate' in json.dumps(execution, ensure_ascii=False)
    doc_only_task = is_doc_only_coding_task(args.input_text, args.allowed_file)
    code_delivery_gate = {
        'status': 'fail' if doc_only_task and not code_delivered else 'pass',
        'reason': 'coding_intent_only_touched_documentation' if doc_only_task and not code_delivered else 'not_doc_only_coding_task',
        'recommended_next_action': 'schedule_implementation_pass' if doc_only_task and not code_delivered else '',
    }
    doc_overproduction = (selected_path == 'governed' and not code_delivered) or code_delivery_gate['status'] == 'fail'
    parallel_denied = selected_path == 'parallel' and not classification.get('independent')
    loop_converged = loop_state.get('status') in {'converged', 'diverging'}
    metrics = update_metrics(
        project,
        path=selected_path,
        status=status_text,
        codex_latency=elapsed,
        fast_path_pre_codex_overhead_ms=pre_codex_overhead_ms if selected_path == 'fast' else 0.0,
        codex_execution_ms=codex_execution_ms,
        code_delivered=code_delivered,
        doc_overproduction=doc_overproduction,
        doc_only_task=doc_only_task,
        code_delivery_gate_failed=code_delivery_gate['status'] == 'fail',
        parallel_denied=parallel_denied,
        loop_converged=loop_converged,
        local_optimization_deferred=local_optimization_deferred,
    )
    fast_path_report = {}
    if selected_path == 'fast':
        fast_path_report = {
            'route': 'fast',
            'skipped_governance': FAST_SKIPPED_GOVERNANCE,
            'codex_latency': elapsed,
            'scope_guard_status': scope_guard_status,
            'tests_status': tests_status,
            'fast_path_pre_codex_overhead_ms': pre_codex_overhead_ms,
            'codex_execution_ms': codex_execution_ms,
            'total_wall_time_ms': total_wall_time_ms,
        }
    report = {
        'schema_version': '4.0',
        'generated_by': 'route_task.py',
        'generated_at': utc_now(),
        'run_id': args.run_id,
        'task_id': args.task_id,
        'workspace': str(project),
        'input': args.input_text,
        'goal_id': goal_id,
        'goal': {'goal_id': goal_id, 'path': goal.get('_path', '')},
        'loop_state': loop_state,
        'classification': classification,
        'route': selected_path,
        'selected_path': selected_path,
        'task_specificity': task_specificity,
        'goal_alignment': alignment,
        'execution': execution,
        'fast_path_report': fast_path_report,
        'fast_path_pre_codex_overhead_ms': pre_codex_overhead_ms if selected_path == 'fast' else 0.0,
        'codex_execution_ms': codex_execution_ms,
        'total_wall_time_ms': total_wall_time_ms,
        'scope_guard_status': scope_guard_status,
        'tests_status': tests_status,
        'local_optimization_deferred': local_optimization_deferred,
        'doc_only_task': doc_only_task,
        'code_delivery_gate': code_delivery_gate,
        'parallel_denial_reason': classification.get('parallel_denial_reason', ''),
        'metrics': metrics.get('metrics', {}),
        'runtime_contract': {
            'cli_runtime': 'control_plane',
            'codex_cli': 'execution_backend',
            'gpt': 'decision_layer',
            'deepseek': 'cheap_analysis_worker',
            'zoo_code': 'optional_ui_layer',
        },
    }
    write_json(report_path, report)
    if selected_path == 'fast' and not args.dry_run and not args.worker_dry_run and execution.get('codex_launched') is not False:
        delivery_outcome, fast_gate, delivery_run, gate_run = run_fast_post_checks(project, args)
        report['delivery_outcome'] = delivery_outcome
        report['fast_path_gate'] = fast_gate
        report['post_execution_checks'] = {
            'delivery_outcome_check': delivery_run,
            'fast_path_gate_check': gate_run,
        }
        report['safety_status'] = 'safe' if fast_gate.get('checks', {}).get('scope_guard_pass') else 'unsafe_or_unknown'
        report['delivery_status'] = fast_gate.get('delivery_outcome') or delivery_outcome.get('delivery_outcome') or 'unknown'
        if fast_gate.get('gate_status') == 'pass':
            returncode = 0
        elif fast_gate.get('verdict') == 'FAST_NO_DELIVERY':
            returncode = 11
        elif fast_gate:
            returncode = 20
        write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return returncode, report


def main() -> int:
    parser = argparse.ArgumentParser(description='CLI-first agent runtime router.')
    parser.add_argument('input', nargs='*')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--input-text', default='')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--task-id', default='')
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--allowed-file', action='append', default=[])
    parser.add_argument('--denied-file', action='append', default=DEFAULT_DENIED_FILES)
    parser.add_argument('--test-command', action='append', default=[])
    parser.add_argument('--changed-file-estimate', type=int, default=0)
    parser.add_argument('--fast', action='store_true')
    parser.add_argument('--parallel', action='store_true')
    parser.add_argument('--governed', action='store_true')
    parser.add_argument('--max-iteration', type=int, default=10)
    parser.add_argument('--max-workers', type=int, default=2)
    parser.add_argument('--start-point', default='HEAD')
    parser.add_argument('--sandbox', default='workspace-write', choices=['read-only', 'workspace-write', 'danger-full-access'])
    parser.add_argument('--profile', default='')
    parser.add_argument('--codex-home', default='')
    parser.add_argument('--timeout-seconds', type=int, default=360)
    parser.add_argument('--no-output-timeout-seconds', type=int, default=600)
    parser.add_argument('--test-timeout-seconds', type=int, default=0)
    parser.add_argument('--max-retries', type=int, default=0)
    parser.add_argument('--discard-failed-worktree', action='store_true')
    parser.add_argument('--ephemeral', action='store_true')
    parser.add_argument('--worker-dry-run', action='store_true')
    parser.add_argument('--skip-health-check', action='store_true')
    parser.add_argument('--allow-ambiguous-fast', action='store_true')
    parser.add_argument('--no-execute-governed-workers', dest='execute_governed_workers', action='store_false')
    parser.add_argument('--dry-run', action='store_true')
    parser.set_defaults(execute_governed_workers=True)
    args = parser.parse_args()

    flags = sum(1 for value in [args.fast, args.parallel, args.governed] if value)
    if flags > 1:
        print('Choose only one of --fast, --parallel, or --governed.', file=sys.stderr)
        return 2
    args.input_text = args.input_text or ' '.join(args.input).strip()
    if not args.input_text:
        print('Missing task input.', file=sys.stderr)
        return 2
    if not args.run_id:
        args.run_id = 'run-' + time.strftime('%Y%m%d%H%M%S', time.gmtime())
    returncode, _ = route_and_execute(args)
    return returncode


if __name__ == '__main__':
    raise SystemExit(main())
