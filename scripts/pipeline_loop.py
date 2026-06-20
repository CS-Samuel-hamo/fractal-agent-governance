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


def pipeline_run(args: argparse.Namespace) -> dict[str, Any]:
    project = project_root(args.workspace)
    objective = args.input_text or ' '.join(args.input).strip()
    if not objective:
        raise SystemExit('Missing pipeline task input.')
    run_id = args.run_id or f'run-pipeline-{time.strftime("%Y%m%d%H%M%S", time.gmtime())}'
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
        ]
        if args.dry_run:
            executor_cmd.append('--dry-run')
        if args.allow_actual:
            executor_cmd.append('--allow-actual')
        if args.codex_home:
            executor_cmd += ['--codex-home', args.codex_home]
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
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--input-text', default='')
    parser.add_argument('--allowed-file', action='append', default=[])
    parser.add_argument('--denied-file', action='append', default=[])
    parser.add_argument('--force-path', choices=['', 'fast', 'parallel', 'governed'], default='')
    parser.add_argument('--max-iterations', type=int, default=1)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--allow-actual', action='store_true')
    parser.add_argument('--sandbox', choices=['read-only', 'workspace-write', 'danger-full-access'], default='workspace-write')
    parser.add_argument('--codex-home', default='')
    parser.add_argument('--timeout-seconds', type=int, default=360)
    args = parser.parse_args()
    report = pipeline_run(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('iterations') else 1


if __name__ == '__main__':
    raise SystemExit(main())
