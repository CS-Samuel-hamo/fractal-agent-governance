#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, utc_now, write_json  # noqa: E402


FORBIDDEN_RESPONSIBILITIES = [
    'goal_selection',
    'scheduling',
    'conflict_detection',
    'resource_arbitration',
    'aggregation',
    'goal_completion',
    'loop_control',
]


def git_name_only(workspace: Path) -> set[str]:
    proc = subprocess.run(
        ['git', 'status', '--short'],
        cwd=workspace,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    files: set[str] = set()
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if ' -> ' in path:
            path = path.split(' -> ', 1)[1].strip()
        files.add(path.replace('\\', '/'))
    return files


def is_runtime_or_generated(path: str) -> bool:
    normalized = path.replace('\\', '/')
    return (
        normalized.startswith('.zoo-agent/')
        or normalized.startswith('.tmp/')
        or normalized.startswith('__pycache__/')
        or '/__pycache__/' in normalized
        or normalized.startswith('.pytest_cache/')
        or normalized.endswith('.pyc')
    )


def matches_any(path: str, patterns: list[str]) -> bool:
    if not patterns:
        return False
    normalized = path.replace('\\', '/')
    for pattern in patterns:
        item = str(pattern).replace('\\', '/')
        if item == normalized or fnmatch.fnmatch(normalized, item):
            return True
        if item.endswith('/**') and normalized.startswith(item[:-3].rstrip('/') + '/'):
            return True
        if item.endswith('*') and normalized.startswith(item[:-1]):
            return True
    return False


def delivery_from_delta(before: set[str], after: set[str], leaf: dict[str, Any], returncode: int) -> dict[str, Any]:
    changed_since_start = sorted(after - before)
    runtime_files = [item for item in changed_since_start if is_runtime_or_generated(item)]
    candidate_files = [item for item in changed_since_start if not is_runtime_or_generated(item)]
    allowed_files = [str(item) for item in leaf.get('allowed_files') or []]
    denied_files = [str(item) for item in leaf.get('denied_files') or []]
    denied_touched = [item for item in candidate_files if matches_any(item, denied_files)]
    out_of_scope = [item for item in candidate_files if allowed_files and not matches_any(item, allowed_files)]
    scope_guard_status = 'pass'
    delivery_outcome = 'delivered'
    reason = 'business_diff_detected'
    if returncode != 0:
        delivery_outcome = 'blocked'
        reason = 'codex_worker_failed'
    elif denied_touched or out_of_scope:
        scope_guard_status = 'fail'
        delivery_outcome = 'unsafe'
        reason = 'scope_guard_failed'
    elif not candidate_files:
        delivery_outcome = 'no_delivery'
        reason = 'no_business_diff_since_executor_start'
    return {
        'delivery_outcome': delivery_outcome,
        'reason': reason,
        'scope_guard_status': scope_guard_status,
        'business_changed_files': candidate_files,
        'runtime_changed_files': runtime_files,
        'denied_files_touched': denied_touched,
        'out_of_scope_files': out_of_scope,
    }


def create_task_pack(task_dir: Path, workspace: Path, leaf: dict[str, Any], plan: dict[str, Any]) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    allowed = leaf.get('allowed_files') or []
    denied = leaf.get('denied_files') or []
    prompt = (
        '# Codex Leaf Execution Task\n\n'
        f'Objective: {leaf.get("objective", "")}\n\n'
        'Constraints:\n'
        '- Execute only this leaf task.\n'
        '- Do not plan, schedule, aggregate, merge, push, or delete worktrees.\n'
        '- Respect allowed and denied file scope.\n\n'
        f'Allowed files: {json.dumps(allowed, ensure_ascii=False)}\n'
        f'Denied files: {json.dumps(denied, ensure_ascii=False)}\n'
    )
    (task_dir / 'CODEX_TASK_PROMPT.md').write_text(prompt, encoding='utf-8')
    (task_dir / 'AGENTS.md').write_text('Codex is execution backend only for this leaf task.\n', encoding='utf-8')
    (task_dir / 'TASKS.yaml').write_text(
        'tasks:\n'
        f'  - id: {leaf.get("leaf_id", "leaf")}\n'
        f'    objective: {json.dumps(leaf.get("objective", ""))[1:-1]}\n'
        f'    allowed_files: {json.dumps(allowed, ensure_ascii=False)}\n'
        f'    denied_files: {json.dumps(denied, ensure_ascii=False)}\n',
        encoding='utf-8',
    )
    (task_dir / 'ACCEPTANCE.md').write_text('\n'.join(str(item) for item in leaf.get('acceptance') or []), encoding='utf-8')
    (task_dir / 'PROGRESS.md').write_text('', encoding='utf-8')
    (task_dir / 'BLOCKERS.md').write_text('', encoding='utf-8')
    (task_dir / 'plan-ref.json').write_text(json.dumps({'plan_run_id': plan.get('run_id')}, indent=2), encoding='utf-8')


def run_codex_leaf(
    *,
    workspace: Path,
    task_dir: Path,
    sandbox: str,
    codex_home: str,
    timeout_seconds: int,
    dry_run: bool,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'run_codex_worker.py'),
        '--workspace',
        str(workspace),
        '--task-dir',
        str(task_dir),
        '--sandbox',
        sandbox,
        '--timeout-seconds',
        str(timeout_seconds),
        '--require-leaf-resolution',
    ]
    if codex_home:
        command += ['--codex-home', codex_home]
    if dry_run:
        command.append('--dry-run')
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
        'command': command,
        'returncode': proc.returncode,
        'stdout_tail': proc.stdout[-4000:],
        'stderr_tail': proc.stderr[-4000:],
        'duration_seconds': round(time.monotonic() - started, 3),
    }


def execute_plan(args: argparse.Namespace) -> dict[str, Any]:
    plan_path = Path(args.plan).resolve()
    plan = load_json(plan_path)
    if not plan:
        raise SystemExit(f'Missing or invalid plan: {plan_path}')
    workspace = Path(plan.get('workspace') or args.workspace or '.').resolve()
    run_id = str(plan.get('run_id') or args.run_id or 'run-pipeline')
    pipeline_dir = plan_path.parent
    leaves = list((plan.get('decomposition') or {}).get('leaf_tasks') or [])
    actual_allowed_by_plan = (plan.get('execution_plan') or {}).get('mode') == 'actual_allowed'
    actual_requested = bool(args.allow_actual and not args.dry_run and actual_allowed_by_plan)
    leaf_results: list[dict[str, Any]] = []
    codex_invoked = False

    for leaf in leaves:
        leaf_id = str(leaf.get('leaf_id') or f'leaf-{len(leaf_results) + 1:03d}')
        task_dir = pipeline_dir / 'executor-task-packs' / leaf_id
        execution_mode = str(leaf.get('execution_mode') or 'dry_run_only')
        leaf_result: dict[str, Any] = {
            'leaf_id': leaf_id,
            'objective': leaf.get('objective', ''),
            'stage': 'executor',
            'input_contract': 'plan.json',
            'route': leaf.get('preferred_route') or (plan.get('execution_plan') or {}).get('route') or 'fast',
            'execution_mode': 'dry_run_only',
            'codex_invoked': False,
            'delivery_outcome': 'dry_run_only',
            'business_changed_files': [],
            'result': 'not_executed_actual_disabled',
        }
        if actual_requested and execution_mode == 'actual_allowed' and leaf.get('resolution') == 'execute':
            create_task_pack(task_dir, workspace, leaf, plan)
            resolution_path = task_dir / 'leaf-resolution.json'
            write_json(
                resolution_path,
                {
                    'leaf_id': leaf_id,
                    'final_resolution': 'execute',
                    'status': 'resolved',
                    'generated_by': 'pipeline_executor.py',
                    'generated_at': utc_now(),
                },
            )
            before_status = git_name_only(workspace)
            codex_result = run_codex_leaf(
                workspace=workspace,
                task_dir=task_dir,
                sandbox=args.sandbox,
                codex_home=args.codex_home,
                timeout_seconds=args.timeout_seconds,
                dry_run=False,
            )
            after_status = git_name_only(workspace)
            codex_invoked = True
            returncode = int(codex_result.get('returncode') or 0)
            delivery = delivery_from_delta(before_status, after_status, leaf, returncode)
            leaf_result.update(
                {
                    'execution_mode': 'actual',
                    'codex_invoked': True,
                    'codex_result': codex_result,
                    **delivery,
                    'result': 'codex_worker_returned',
                }
            )
            if returncode != 0:
                leaf_result['result'] = 'codex_worker_failed'
        leaf_results.append(leaf_result)

    return {
        'schema_version': '1.0',
        'generated_by': 'pipeline_executor.py',
        'generated_at': utc_now(),
        'stage': 'executor',
        'run_id': run_id,
        'workspace': str(workspace),
        'plan_ref': str(plan_path),
        'input_contract': 'plan.json',
        'output_contract': 'execution_result.json',
        'forbidden_responsibilities': FORBIDDEN_RESPONSIBILITIES,
        'scheduler_used': False,
        'conflict_detector_used': False,
        'aggregation_used': False,
        'codex_backend': {
            'allowed_in_stage': True,
            'invoked': codex_invoked,
            'actual_requested': actual_requested,
            'reason': 'actual disabled unless --allow-actual and plan execution_mode=actual_allowed',
        },
        'execution_summary': {
            'leaf_count': len(leaves),
            'actual_leaf_count': sum(1 for item in leaf_results if item.get('codex_invoked')),
            'dry_run_leaf_count': sum(1 for item in leaf_results if not item.get('codex_invoked')),
        },
        'leaf_results': leaf_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Executor stage for the 3-stage Agent Runtime pipeline.')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--output', default='')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--allow-actual', action='store_true')
    parser.add_argument('--sandbox', choices=['read-only', 'workspace-write', 'danger-full-access'], default='workspace-write')
    parser.add_argument('--codex-home', default='')
    parser.add_argument('--timeout-seconds', type=int, default=360)
    args = parser.parse_args()
    result = execute_plan(args)
    output = Path(args.output).resolve() if args.output else Path(args.plan).resolve().parent / 'execution_result.json'
    write_json(output, result)
    print(json.dumps({'status': 'ok', 'execution_result_json': str(output), 'run_id': result['run_id'], 'stage': 'executor'}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
