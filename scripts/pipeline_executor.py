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
from execution_fallback_router import fallback_decision  # noqa: E402
from execution_health_scoring import score_execution_health  # noqa: E402
from execution_level_splitter import split_leaf_execution  # noqa: E402
from execution_result_model import build_execution_result_model, delivery_outcome_from_execution_status  # noqa: E402
from execution_retry_controller import retry_decision  # noqa: E402


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


def parse_json_object(text: str) -> dict[str, Any]:
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try:
            payload = json.loads(text[start : end + 1])
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}
    return {}


def worker_status_from_codex_result(codex_result: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_json_object(str(codex_result.get('stdout') or codex_result.get('stdout_tail') or ''))
    worker_status = parsed.get('worker_status') if isinstance(parsed.get('worker_status'), dict) else {}
    if not worker_status and parsed.get('status'):
        worker_status = parsed
    status = str(worker_status.get('status') or '')
    return {
        'status': status,
        'returncode': int(worker_status.get('returncode') if worker_status.get('returncode') is not None else codex_result.get('returncode') or 0),
        'transient_failure_suspected': bool(worker_status.get('transient_failure_suspected') or parsed.get('timed_out')),
        'worker_status': worker_status,
        'parsed_stdout': parsed,
    }


def expected_files_for_leaf(leaf: dict[str, Any]) -> list[str]:
    expected: list[str] = []
    for item in leaf.get('allowed_files') or []:
        value = str(item).replace('\\', '/')
        if not value or any(ch in value for ch in '*?[]'):
            continue
        expected.append(value)
    return expected


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


def execute_leaf_once(
    *,
    workspace: Path,
    task_dir: Path,
    leaf: dict[str, Any],
    plan: dict[str, Any],
    sandbox: str,
    codex_home: str,
    timeout_seconds: int,
    attempt_no: int,
    fallback_used: str,
) -> dict[str, Any]:
    create_task_pack(task_dir, workspace, leaf, plan)
    write_json(
        task_dir / 'leaf-resolution.json',
        {
            'leaf_id': leaf.get('leaf_id', 'leaf'),
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
        sandbox=sandbox,
        codex_home=codex_home,
        timeout_seconds=timeout_seconds,
        dry_run=False,
    )
    after_status = git_name_only(workspace)
    worker = worker_status_from_codex_result(codex_result)
    returncode = int(worker.get('returncode') or 0)
    delivery = delivery_from_delta(before_status, after_status, leaf, returncode)
    model = build_execution_result_model(
        task_id=str(leaf.get('leaf_id') or 'leaf'),
        codex_returncode=returncode,
        worker_status=str(worker.get('status') or ''),
        business_changed_files=delivery.get('business_changed_files') or [],
        expected_files=expected_files_for_leaf(leaf),
        denied_files_touched=delivery.get('denied_files_touched') or [],
        out_of_scope_files=delivery.get('out_of_scope_files') or [],
        execution_time=codex_result.get('duration_seconds', ''),
        retry_count=max(0, attempt_no - 1),
        fallback_used=fallback_used,
        notes=delivery.get('reason', ''),
    )
    if model['execution_status'] in {'timeout', 'partial', 'failed'} and delivery.get('delivery_outcome') != 'unsafe':
        delivery['delivery_outcome'] = delivery_outcome_from_execution_status(str(model['execution_status']))
        delivery['reason'] = model.get('reason') or delivery.get('reason')
    write_json(task_dir / 'execution-result-model.json', model)
    return {
        'attempt': attempt_no,
        'task_dir': str(task_dir),
        'codex_result': codex_result,
        'worker_status': worker,
        'delivery': delivery,
        'execution_model': model,
    }


def execute_unit_with_retries(
    *,
    workspace: Path,
    task_dir: Path,
    leaf: dict[str, Any],
    plan: dict[str, Any],
    sandbox: str,
    codex_home: str,
    timeout_seconds: int,
    max_retries: int,
    fallback_used: str,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for attempt_no in range(1, max_retries + 2):
        attempt_dir = task_dir / f'attempt-{attempt_no:02d}'
        attempt = execute_leaf_once(
            workspace=workspace,
            task_dir=attempt_dir,
            leaf=leaf,
            plan=plan,
            sandbox=sandbox,
            codex_home=codex_home,
            timeout_seconds=timeout_seconds,
            attempt_no=attempt_no,
            fallback_used=fallback_used if fallback_used else ('retry_codex' if attempt_no > 1 else ''),
        )
        model = attempt['execution_model']
        delivery = attempt['delivery']
        decision = retry_decision(model, attempt=attempt_no, max_retries=max_retries)
        attempt['retry_decision'] = decision
        attempts.append(attempt)
        if model.get('execution_status') == 'success' or delivery.get('delivery_outcome') == 'unsafe':
            return {'status': 'done', 'attempts': attempts, 'final_attempt': attempt}
        if not decision.get('should_retry'):
            return {'status': 'needs_fallback', 'attempts': attempts, 'final_attempt': attempt}
    return {'status': 'needs_fallback', 'attempts': attempts, 'final_attempt': attempts[-1] if attempts else {}}


def resilient_execute_leaf(
    *,
    workspace: Path,
    task_dir: Path,
    leaf: dict[str, Any],
    plan: dict[str, Any],
    sandbox: str,
    codex_home: str,
    timeout_seconds: int,
    max_retries: int,
) -> dict[str, Any]:
    fallback_history: list[str] = []
    primary = execute_unit_with_retries(
        workspace=workspace,
        task_dir=task_dir / 'primary',
        leaf=leaf,
        plan=plan,
        sandbox=sandbox,
        codex_home=codex_home,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        fallback_used='',
    )
    attempts = list(primary.get('attempts') or [])
    final_attempt = primary.get('final_attempt') or {}
    final_model = final_attempt.get('execution_model') or {}
    final_delivery = final_attempt.get('delivery') or {}
    split_results: list[dict[str, Any]] = []
    fallback_used = ''

    if final_model.get('execution_status') != 'success' and final_delivery.get('delivery_outcome') != 'unsafe':
        retryable = bool((final_attempt.get('retry_decision') or {}).get('retryable'))
        split_available = True
        decision = fallback_decision(final_model, retry_available=False if attempts else retryable, split_available=split_available, fallback_history=fallback_history)
        action = str(decision.get('action') or '')
        fallback_history.append(action)
        if action in {'split_execution', 'reduce_scope_execution'}:
            chunks = split_leaf_execution(leaf, reason=action)
            for index, chunk in enumerate(chunks, start=1):
                result = execute_unit_with_retries(
                    workspace=workspace,
                    task_dir=task_dir / action / f'chunk-{index:02d}',
                    leaf=chunk,
                    plan=plan,
                    sandbox=sandbox,
                    codex_home=codex_home,
                    timeout_seconds=max(60, min(timeout_seconds, timeout_seconds // 2 if timeout_seconds > 120 else timeout_seconds)),
                    max_retries=0,
                    fallback_used=action,
                )
                split_results.append(result)
            split_attempts = [item.get('final_attempt') or {} for item in split_results]
            if split_attempts and all((item.get('execution_model') or {}).get('execution_status') == 'success' for item in split_attempts):
                business_files = sorted(
                    {
                        path
                        for item in split_attempts
                        for path in ((item.get('delivery') or {}).get('business_changed_files') or [])
                    }
                )
                merged_model = build_execution_result_model(
                    task_id=str(leaf.get('leaf_id') or 'leaf'),
                    codex_returncode=0,
                    worker_status='succeeded',
                    business_changed_files=business_files,
                    expected_files=expected_files_for_leaf(leaf),
                    retry_count=max(0, len(attempts) - 1),
                    fallback_used=action,
                    notes='split_execution_succeeded',
                )
                final_model = merged_model
                final_delivery = {
                    'delivery_outcome': 'delivered',
                    'reason': 'split_execution_delivered',
                    'scope_guard_status': 'pass',
                    'business_changed_files': business_files,
                    'runtime_changed_files': [],
                    'denied_files_touched': [],
                    'out_of_scope_files': [],
                }
                fallback_used = action
            else:
                fallback_used = 'dry_run_mode'
                fallback_history.append('dry_run_mode')
                final_delivery = {
                    'delivery_outcome': 'dry_run_only',
                    'reason': 'fallback_to_dry_run_after_execution_failure',
                    'scope_guard_status': 'not_run_fallback_dry_run',
                    'business_changed_files': [],
                    'runtime_changed_files': [],
                    'denied_files_touched': [],
                    'out_of_scope_files': [],
                }
                if final_model:
                    final_model = dict(final_model)
                    final_model['fallback_used'] = fallback_used
        else:
            fallback_used = action

    return {
        'attempts': attempts,
        'split_results': split_results,
        'fallback_history': fallback_history,
        'fallback_used': fallback_used,
        'final_model': final_model,
        'final_delivery': final_delivery,
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
            resilient = resilient_execute_leaf(
                workspace=workspace,
                task_dir=task_dir,
                leaf=leaf,
                plan=plan,
                sandbox=args.sandbox,
                codex_home=args.codex_home,
                timeout_seconds=args.timeout_seconds,
                max_retries=args.max_retries,
            )
            codex_invoked = True
            final_delivery = resilient.get('final_delivery') or {}
            final_model = resilient.get('final_model') or {}
            attempt_count = len(resilient.get('attempts') or [])
            leaf_result.update(
                {
                    'execution_mode': 'actual',
                    'codex_invoked': True,
                    'codex_result': (resilient.get('attempts') or [{}])[-1].get('codex_result', {}),
                    'retry_history': resilient.get('attempts') or [],
                    'split_results': resilient.get('split_results') or [],
                    'fallback_chain': ['retry_codex', 'split_execution', 'reduce_scope_execution', 'dry_run_mode', 'escalate_to_planner'],
                    'fallback_history': resilient.get('fallback_history') or [],
                    'fallback_used': resilient.get('fallback_used') or '',
                    'execution_model': final_model,
                    'execution_status': final_model.get('execution_status') or 'unknown',
                    **final_delivery,
                    'result': 'codex_worker_resilient_execution',
                }
            )
            if final_delivery.get('delivery_outcome') == 'dry_run_only':
                leaf_result['result'] = 'fallback_dry_run_after_execution_failure'
            elif final_delivery.get('delivery_outcome') == 'blocked':
                leaf_result['result'] = 'fallback_exhausted'
            leaf_result['retry_count'] = max(0, attempt_count - 1)
        leaf_results.append(leaf_result)

    execution_models = [item.get('execution_model') for item in leaf_results if isinstance(item.get('execution_model'), dict)]
    health = score_execution_health(execution_models)

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
            'retry_count': sum(int(item.get('retry_count') or 0) for item in leaf_results),
            'fallback_count': sum(1 for item in leaf_results if item.get('fallback_used')),
        },
        'execution_resilience': {
            'enabled': True,
            'max_retries': args.max_retries,
            'fallback_chain': ['retry_codex', 'split_execution', 'reduce_scope_execution', 'dry_run_mode', 'escalate_to_planner'],
            'health_score': health,
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
    parser.add_argument('--max-retries', type=int, default=2)
    args = parser.parse_args()
    result = execute_plan(args)
    output = Path(args.output).resolve() if args.output else Path(args.plan).resolve().parent / 'execution_result.json'
    write_json(output, result)
    print(json.dumps({'status': 'ok', 'execution_result_json': str(output), 'run_id': result['run_id'], 'stage': 'executor'}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
