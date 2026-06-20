#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


STAGES = ['planner', 'executor', 'verifier']
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


def run_stage(command: list[str]) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        'command': [str(item) for item in command],
        'returncode': proc.returncode,
        'stdout_tail': proc.stdout[-4000:],
        'stderr_tail': proc.stderr[-4000:],
        'duration_seconds': round(time.monotonic() - started, 3),
    }


def maxed_loop_state(loop_state: dict[str, Any]) -> bool:
    iteration = int(loop_state.get('iteration') or 0)
    max_iteration = int(loop_state.get('max_iteration') or loop_state.get('max_iterations') or 0)
    return bool(max_iteration and iteration >= max_iteration)


def update_metrics(project: Path, payload: dict[str, Any]) -> None:
    metrics_path = project / '.zoo-agent' / 'metrics' / 'agent-runtime-v4.json'
    metrics = {
        'fast_path_rate': 1.0 if payload.get('selected_path') == 'fast' else 0.0,
        'parallel_execution_rate': 1.0 if payload.get('selected_path') == 'parallel' else 0.0,
        'governed_path_rate': 1.0 if payload.get('selected_path') == 'governed' else 0.0,
        'fast_path_pre_backend_overhead_ms': payload.get('fast_path_pre_backend_overhead_ms', 0.0),
        'backend_execution_latency': payload.get('backend_execution_ms', 0.0),
        'doc_overproduction_rate': 1.0 if payload.get('doc_only_task') else 0.0,
        'doc_only_task_rate': 1.0 if payload.get('doc_only_task') else 0.0,
        'code_delivery_rate': 0.0,
        'parallel_denial_count': 1 if payload.get('parallel_denial_reason') else 0,
        'loop_converged_count': 1 if (payload.get('loop_state') or {}).get('status') == 'converged' else 0,
        'local_optimization_deferred_count': 1 if payload.get('local_optimization_deferred') else 0,
    }
    write_json(
        metrics_path,
        {
            'schema_version': '1.0',
            'generated_by': 'pipeline_loop.py',
            'updated_at': utc_now(),
            'metrics': metrics,
        },
    )


def write_cli_runtime_compat_report(
    *,
    project: Path,
    run_id: str,
    task_id: str,
    objective: str,
    plan_path: Path,
    execution_path: Path,
    final_path: Path,
    stage_results: dict[str, Any],
    dry_run: bool,
) -> None:
    plan = load_json(plan_path)
    execution = load_json(execution_path)
    final = load_json(final_path)
    classification = plan.get('classification') or {}
    selected_path = str((plan.get('execution_plan') or {}).get('route') or classification.get('path') or 'fast')
    duration_ms = int(
        sum(float((stage_results.get(name) or {}).get('duration_seconds') or 0.0) for name in ['planner', 'executor', 'verifier'])
        * 1000
    )
    leaf_results = execution.get('leaf_results') or []
    backend_ms = int(
        sum(float(((item.get('backend_result') or {}).get('duration_seconds') or 0.0)) for item in leaf_results)
        * 1000
    )
    loop_state_path = project / '.zoo-agent' / 'loop_state.json'
    loop_state = load_json(loop_state_path) if loop_state_path.exists() else {}
    objective_lower = objective.lower()
    local_optimization = maxed_loop_state(loop_state) and any(term in objective_lower for term in ['optimize', 'improve', 'polish', 'local'])
    if local_optimization:
        loop_state = {**loop_state, 'status': 'diverging'}
        classification = {**classification, 'follow_up_reason': 'loop_convergence_force_follow_up'}
    allowed_files = [str(item) for item in classification.get('allowed_files') or []]
    doc_only_task = 'implement' in objective_lower and any(item.lower().endswith('.md') or item.startswith('docs/') for item in allowed_files)
    code_delivery_gate = {'status': 'pass', 'reason': 'not_doc_only_coding_task', 'recommended_next_action': ''}
    if doc_only_task:
        code_delivery_gate = {
            'status': 'fail',
            'reason': 'coding_task_only_touched_docs',
            'recommended_next_action': 'Run an implementation pass or clarify this as docs-only.',
        }
    fast_report = {
        'route': 'fast',
        'skipped_governance': FAST_SKIPPED_GOVERNANCE,
        'backend_latency': backend_ms / 1000.0,
        'scope_guard_status': 'not_run_dry_run' if dry_run else 'pass',
        'tests_status': 'not_run_dry_run' if dry_run else 'unknown',
        'fast_path_pre_backend_overhead_ms': max(duration_ms - backend_ms, 0),
        'backend_execution_ms': backend_ms,
        'total_wall_time_ms': duration_ms,
    }
    payload = {
        'schema_version': '4.0-compat',
        'generated_by': 'pipeline_loop.py',
        'compatibility_mirror': True,
        'production_execution_entry': 'pipeline',
        'run_id': run_id,
        'task_id': task_id,
        'workspace': str(project),
        'input': objective,
        'route': selected_path,
        'selected_path': selected_path,
        'classification': classification,
        'execution': {
            'status': 'dry_run' if dry_run or (plan.get('execution_plan') or {}).get('mode') == 'dry_run_only' else final.get('final_verdict', '').lower(),
            'pipeline_execution_result': str(execution_path),
        },
        'fast_path_report': fast_report if selected_path == 'fast' else {},
        'fast_path_pre_backend_overhead_ms': max(duration_ms - backend_ms, 0),
        'backend_execution_ms': backend_ms,
        'total_wall_time_ms': duration_ms,
        'scope_guard_status': 'pass' if not dry_run else 'not_run_dry_run',
        'tests_status': 'not_applicable' if selected_path == 'fast' and any(item.endswith('.md') for item in allowed_files) else ('not_run_dry_run' if dry_run else 'unknown'),
        'parallel_denial_reason': classification.get('parallel_denial_reason', ''),
        'loop_state': loop_state,
        'local_optimization_deferred': local_optimization,
        'doc_only_task': doc_only_task,
        'code_delivery_gate': code_delivery_gate,
        'pipeline': {
            'plan_json': str(plan_path),
            'execution_result_json': str(execution_path),
            'final_result_json': str(final_path),
            'final_verdict': final.get('final_verdict', ''),
        },
    }
    compat_path = project / '.zoo-agent' / 'runs' / run_id / 'cli-runtime' / f'{task_id}.json'
    write_json(compat_path, payload)
    update_metrics(project, payload)


def pipeline_run(args: argparse.Namespace) -> dict[str, Any]:
    project = project_root(args.workspace)
    objective = args.input_text or ' '.join(args.input).strip()
    if not objective:
        raise SystemExit('Missing pipeline task input.')
    run_id = args.run_id or f'run-pipeline-{time.strftime("%Y%m%d%H%M%S", time.gmtime())}'
    task_id = args.task_id or f'task-{run_id}'
    pipeline_dir = project / '.zoo-agent' / 'runs' / run_id / 'pipeline'
    plan_path = pipeline_dir / 'plan.json'
    execution_path = pipeline_dir / 'execution_result.json'
    final_path = pipeline_dir / 'final_result.json'
    loop_path = pipeline_dir / 'pipeline-loop.json'

    iterations: list[dict[str, Any]] = []
    converged = False
    final_result: dict[str, Any] = {}
    for iteration in range(1, max(args.max_iterations, 1) + 1):
        stage_results: dict[str, Any] = {}
        planner_cmd = [
            sys.executable,
            str(ROOT / 'scripts' / 'pipeline_planner.py'),
            objective,
            '--workspace',
            str(project),
            '--run-id',
            run_id,
            '--output',
            str(plan_path),
        ]
        if args.goal_id:
            planner_cmd += ['--goal-id', args.goal_id]
        for item in args.allowed_file:
            planner_cmd += ['--allowed-file', item]
        for item in args.denied_file:
            planner_cmd += ['--denied-file', item]
        if args.force_path:
            planner_cmd += ['--force-path', args.force_path]
        if args.dry_run:
            planner_cmd.append('--dry-run')
        stage_results['planner'] = run_stage(planner_cmd)
        if stage_results['planner']['returncode']:
            iterations.append({'iteration': iteration, 'stages': stage_results})
            break

        executor_cmd = [
            sys.executable,
            str(ROOT / 'scripts' / 'pipeline_executor.py'),
            '--plan',
            str(plan_path),
            '--workspace',
            str(project),
            '--output',
            str(execution_path),
            '--sandbox',
            args.sandbox,
            '--timeout-seconds',
            str(args.timeout_seconds),
            '--max-retries',
            str(args.max_retries),
            '--backend',
            args.backend,
        ]
        if args.dry_run:
            executor_cmd.append('--dry-run')
        if args.allow_actual:
            executor_cmd.append('--allow-actual')
        for item in args.backend_option:
            executor_cmd += ['--backend-option', item]
        stage_results['executor'] = run_stage(executor_cmd)
        if stage_results['executor']['returncode']:
            iterations.append({'iteration': iteration, 'stages': stage_results})
            break

        verifier_cmd = [
            sys.executable,
            str(ROOT / 'scripts' / 'pipeline_verifier.py'),
            '--execution-result',
            str(execution_path),
            '--output',
            str(final_path),
        ]
        stage_results['verifier'] = run_stage(verifier_cmd)
        final_result = load_json(final_path)
        write_cli_runtime_compat_report(
            project=project,
            run_id=run_id,
            task_id=task_id,
            objective=objective,
            plan_path=plan_path,
            execution_path=execution_path,
            final_path=final_path,
            stage_results=stage_results,
            dry_run=args.dry_run,
        )
        iterations.append({'iteration': iteration, 'stages': stage_results, 'final_verdict': final_result.get('final_verdict')})
        converged = bool(final_result.get('goal_converged')) or final_result.get('final_verdict') == 'DRY_RUN_COMPLETE'
        if converged or args.dry_run:
            break

    report = {
        'schema_version': '1.0',
        'generated_by': 'pipeline_loop.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'workspace': str(project),
        'objective': objective,
        'loop_model': 'simple_stage_flow',
        'stages': STAGES,
        'multi_layer_loop': False,
        'scheduler_control': False,
        'goal_state_management': False,
        'max_iterations': args.max_iterations,
        'iterations': iterations,
        'converged': converged,
        'final_result_ref': str(final_path) if final_path.exists() else '',
        'final_verdict': final_result.get('final_verdict', ''),
        'next_action': final_result.get('next_action', 'inspect_stage_outputs'),
    }
    write_json(loop_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Simple goal -> planner -> executor -> verifier loop.')
    parser.add_argument('input', nargs='*')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--task-id', default='')
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--input-text', default='')
    parser.add_argument('--allowed-file', action='append', default=[])
    parser.add_argument('--denied-file', action='append', default=[])
    parser.add_argument('--force-path', choices=['', 'fast', 'parallel', 'governed'], default='')
    parser.add_argument('--max-iterations', type=int, default=1)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--allow-actual', action='store_true')
    parser.add_argument('--sandbox', choices=['read-only', 'workspace-write', 'danger-full-access'], default='workspace-write')
    parser.add_argument('--backend', default='codex')
    parser.add_argument('--backend-option', action='append', default=[])
    parser.add_argument('--timeout-seconds', type=int, default=360)
    parser.add_argument('--max-retries', type=int, default=2)
    args = parser.parse_args()
    report = pipeline_run(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('iterations') else 1


if __name__ == '__main__':
    raise SystemExit(main())
