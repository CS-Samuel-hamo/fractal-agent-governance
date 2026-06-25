#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from execution_policy import DEFAULT_DENIED_FILES, detect_hard_risk

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


def utc_now() -> str:
    return datetime.datetime.utcnow().isoformat() + 'Z'


def safe_name(value: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in '._-' else '-' for ch in value).strip('-') or 'task'


def short_name(value: str, limit: int = 32) -> str:
    safe = safe_name(value)
    if len(safe) <= limit:
        return safe
    digest = hashlib.sha1(value.encode('utf-8', errors='replace')).hexdigest()[:8]
    return f'{safe[: max(1, limit - 9)]}-{digest}'


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def run_command(cmd, cwd: Path, *, env=None, shell=False, timeout=None) -> dict:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            shell=shell,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            env=env,
            timeout=timeout,
        )
        return {
            'command': cmd if isinstance(cmd, str) else [str(x) for x in cmd],
            'cwd': str(cwd),
            'returncode': proc.returncode,
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'command': cmd if isinstance(cmd, str) else [str(x) for x in cmd],
            'cwd': str(cwd),
            'returncode': 124,
            'stdout': exc.stdout or '',
            'stderr': exc.stderr or '',
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': True,
        }


def git_output(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        ['git', *args],
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or f'git command failed: {args}')
    return proc.stdout.strip()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def parse_json_text(text: str) -> dict:
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def append_retry_context(task_dir: Path, evidence: str) -> None:
    prompt = task_dir / 'CODEX_TASK_PROMPT.md'
    retry_context = task_dir / 'RETRY_CONTEXT.md'
    retry_context.write_text(evidence, encoding='utf-8')
    current = prompt.read_text(encoding='utf-8')
    prompt.write_text(
        current + '\n\nRetry context from the previous isolated attempt:\n' + evidence[:6000] + '\n',
        encoding='utf-8',
    )


def summarize_failure(attempt: dict) -> str:
    parts = []
    codex = attempt.get('codex_worker', {})
    if codex.get('returncode') not in (None, 0):
        parts.append(f'Codex worker exited with {codex.get("returncode")}.')
        if codex.get('stderr'):
            parts.append('Worker stderr tail:\n' + codex['stderr'][-2500:])
    for result in attempt.get('test_results', []):
        if result.get('returncode') != 0:
            parts.append(f'Test failed: {result.get("command")}')
            output = (result.get('stdout') or '') + (result.get('stderr') or '')
            parts.append(output[-3500:])
    return '\n\n'.join(parts) or 'Previous attempt failed without detailed output.'


def create_worktree(
    repo_root: Path, worktree_root: Path, run_id: str, task_id: str, attempt: int, start_point: str
) -> tuple[Path, str, dict]:
    timestamp = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    safe_run = short_name(run_id, 28)
    safe_task = short_name(task_id, 36)
    branch_name = f'zoo/{safe_run}/{safe_task}/attempt-{attempt}-{timestamp}'
    worktree_path = worktree_root / f'attempt-{attempt}'
    if worktree_path.exists():
        worktree_path = worktree_root / f'attempt-{attempt}-{timestamp}'
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(['git', 'worktree', 'add', '-b', branch_name, str(worktree_path), start_point], repo_root)
    return worktree_path.resolve(), branch_name, result


def generate_task_pack(args, task_id: str, task_dir: Path, worktree_path: Path) -> dict:
    cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'generate_codex_task_pack.py'),
        '--run-id',
        args.run_id,
        '--task-id',
        task_id,
        '--objective',
        args.objective,
        '--goal-id',
        args.goal_id,
        '--worktree',
        str(worktree_path),
        '--output',
        str(task_dir),
        '--prompt-template',
        'CODEX_TASK_PROMPT_FAST.md' if args.fast_prompt else 'CODEX_TASK_PROMPT.md',
    ]
    if args.task_context:
        cmd += ['--task-context', args.task_context]
    for pattern in args.allowed_file:
        cmd += ['--allowed-file', pattern]
    for pattern in args.denied_file:
        cmd += ['--denied-file', pattern]
    for command in args.test_command:
        cmd += ['--test-command', command]
    return run_command(cmd, ROOT)


def run_codex_worker(args, task_dir: Path, worktree_path: Path) -> dict:
    cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'run_codex_worker.py'),
        '--task-dir',
        str(task_dir),
        '--workspace',
        str(worktree_path),
        '--sandbox',
        args.sandbox,
        '--timeout-seconds',
        str(args.timeout_seconds),
        '--no-output-timeout-seconds',
        str(args.no_output_timeout_seconds),
    ]
    if args.codex_home:
        cmd += ['--codex-home', args.codex_home]
    if args.profile:
        cmd += ['--profile', args.profile]
    if args.ephemeral:
        cmd += ['--ephemeral']
    if args.json_events:
        cmd += ['--json-events']
    if args.skip_git_repo_check:
        cmd += ['--skip-git-repo-check']
    return run_command(cmd, ROOT, timeout=args.timeout_seconds + 30 if args.timeout_seconds > 0 else None)


def run_tests(test_commands: list[str], worktree_path: Path, timeout_seconds: int) -> list[dict]:
    results = []
    env = os.environ.copy()
    tmp = worktree_path / '.zoo-agent' / 'tmp' / 'harness'
    tmp.mkdir(parents=True, exist_ok=True)
    env['TMP'] = str(tmp)
    env['TEMP'] = str(tmp)
    env['TMPDIR'] = str(tmp)
    env['PYTHONPYCACHEPREFIX'] = str(tmp / 'pycache')
    for command in test_commands:
        results.append(run_command(command, worktree_path, shell=True, env=env, timeout=timeout_seconds or None))
    return results


def capture_task_baseline(args, task_id: str, worktree_path: Path) -> dict:
    cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'capture_task_baseline.py'),
        '--run-id',
        args.run_id,
        '--task-id',
        task_id,
        '--workspace',
        str(worktree_path),
        '--route',
        'fast' if args.fast_prompt else args.execution_path,
        '--input-text',
        args.objective,
        '--output',
        str(
            worktree_path
            / '.zoo-agent'
            / 't'
            / short_name(args.run_id, 18)
            / short_name(task_id, 24)
            / 'task-baseline.json'
        ),
    ]
    for pattern in args.allowed_file:
        cmd += ['--allowed-file', pattern]
    for pattern in args.denied_file:
        cmd += ['--denied-file', pattern]
    result = run_command(cmd, ROOT)
    payload = {}
    try:
        payload = json.loads(result.get('stdout') or '{}')
    except Exception:
        payload = {}
    return {'command_result': result, 'path': payload.get('path', ''), 'payload': payload}


def compare_task_baseline(args, baseline_path: str, worktree_path: Path, task_id: str) -> dict:
    if not baseline_path:
        return {'command_result': {'returncode': 2, 'stderr': 'missing baseline path'}, 'path': '', 'payload': {}}
    cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'compare_task_baseline.py'),
        '--baseline',
        baseline_path,
        '--workspace',
        str(worktree_path),
        '--output',
        str(
            worktree_path
            / '.zoo-agent'
            / 't'
            / short_name(args.run_id, 18)
            / short_name(task_id, 24)
            / 'task-delta.json'
        ),
    ]
    for pattern in args.denied_file:
        cmd += ['--denied-file', pattern]
    result = run_command(cmd, ROOT)
    payload = {}
    try:
        payload = json.loads(result.get('stdout') or '{}')
    except Exception:
        payload = {}
    return {'command_result': result, 'path': payload.get('path', ''), 'payload': payload}


def collect_result(args, task_id: str, task_dir: Path, worktree_path: Path) -> tuple[dict, dict | None]:
    cmd = [
        sys.executable,
        str(ROOT / 'scripts' / 'collect_codex_result.py'),
        '--run-id',
        args.run_id,
        '--task-id',
        task_id,
        '--task-dir',
        str(task_dir),
        '--workspace',
        str(worktree_path),
    ]
    collect = run_command(cmd, worktree_path)
    result_json = worktree_path / '.zoo-agent' / 'runs' / args.run_id / 'codex-results' / task_id / 'result.json'
    output_lines = [line.strip() for line in str(collect.get('stdout') or '').splitlines() if line.strip()]
    if output_lines:
        candidate = Path(output_lines[-1]) / 'result.json'
        if candidate.exists():
            result_json = candidate
    parsed = None
    if result_json.exists():
        parsed = json.loads(result_json.read_text(encoding='utf-8'))
    return collect, parsed


def choose_policy(codex_result: dict, test_results: list[dict], collected: dict | None) -> dict:
    scope = (collected or {}).get('scope_guard', {})
    scope_status = scope.get('status', 'not_run')
    failed_tests = [r for r in test_results if r.get('returncode') != 0]
    worker_status = (
        (collected or {}).get('worker_status') if isinstance((collected or {}).get('worker_status'), dict) else {}
    )
    worker_state = str(worker_status.get('status') or '')

    if worker_state in {'timeout', 'no_output_timeout', 'spawn_failed', 'exception'}:
        return {
            'status': 'retryable_worker_failure',
            'recommended_next_action': 'inspect_codex_worker_status_and_logs_before_retry',
            'retryable': True,
        }
    if codex_result.get('returncode') != 0:
        return {
            'status': 'retryable_worker_failure',
            'recommended_next_action': 'retry_with_worker_output_or_escalate_if_repeated',
            'retryable': True,
        }
    if scope_status == 'fail':
        return {
            'status': 'escalate_scope_violation',
            'recommended_next_action': 'stop_and_expand_scope_or_review_diff',
            'retryable': False,
        }
    if failed_tests:
        return {
            'status': 'retryable_test_failure',
            'recommended_next_action': 'retry_once_with_test_output',
            'retryable': True,
        }
    if scope_status != 'pass':
        return {
            'status': 'verification_partial',
            'recommended_next_action': 'review_manually_or_run_scope_guard',
            'retryable': False,
        }
    if not test_results:
        return {
            'status': 'merge_candidate_partial',
            'recommended_next_action': 'review_diff_and_run_targeted_tests_before_merge',
            'retryable': False,
        }
    return {
        'status': 'merge_candidate',
        'recommended_next_action': 'review_diff_then_merge_candidate',
        'retryable': False,
    }


def fast_contract(
    *, pre_codex_ms: float, codex_ms: float, total_ms: float, scope_status: str, tests_status: str
) -> dict:
    return {
        'route': 'fast',
        'skipped_governance': FAST_SKIPPED_GOVERNANCE,
        'codex_latency': round(codex_ms / 1000, 3) if codex_ms else 0.0,
        'scope_guard_status': scope_status,
        'tests_status': tests_status,
        'fast_path_pre_codex_overhead_ms': pre_codex_ms,
        'codex_execution_ms': codex_ms,
        'total_wall_time_ms': total_ms,
    }


def maybe_discard_worktree(repo_root: Path, worktree_path: Path, worktree_root: Path) -> dict | None:
    resolved = worktree_path.resolve()
    allowed_root = worktree_root.resolve()
    if not is_relative_to(resolved, allowed_root):
        return {
            'skipped': True,
            'reason': f'worktree path is outside managed root: {resolved}',
        }
    return run_command(['git', 'worktree', 'remove', '--force', str(resolved)], repo_root)


def main() -> int:
    wall_started = time.monotonic()
    ap = argparse.ArgumentParser(
        description='Run a cheap-risk-gated optimistic Codex worker in an isolated git worktree.'
    )
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--workspace', required=True, help='Existing git workspace/repo root used as the base')
    ap.add_argument('--objective', required=True)
    ap.add_argument('--goal-id', default='')
    ap.add_argument('--allowed-file', action='append', default=[])
    ap.add_argument('--denied-file', action='append', default=DEFAULT_DENIED_FILES)
    ap.add_argument('--test-command', action='append', default=[])
    ap.add_argument(
        '--task-context', default='', help='Optional task context JSON/Markdown file to copy into the task pack'
    )
    ap.add_argument(
        '--worktree-root',
        default='',
        help='Managed worktree root; defaults to <repo>/.zoo-agent/worktrees/<run>/<task>',
    )
    ap.add_argument('--start-point', default='HEAD')
    ap.add_argument(
        '--sandbox', default='workspace-write', choices=['read-only', 'workspace-write', 'danger-full-access']
    )
    ap.add_argument('--execution-path', default='optimistic_worker', choices=['optimistic_worker', 'planned_worker'])
    ap.add_argument('--profile', default='')
    ap.add_argument('--codex-home', default='')
    ap.add_argument('--timeout-seconds', type=int, default=360)
    ap.add_argument('--no-output-timeout-seconds', type=int, default=600)
    ap.add_argument('--test-timeout-seconds', type=int, default=0)
    ap.add_argument('--max-retries', type=int, default=0)
    ap.add_argument('--allow-hard-risk', action='store_true')
    ap.add_argument('--fast-prompt', action='store_true', default=True)
    ap.add_argument('--full-prompt', dest='fast_prompt', action='store_false')
    ap.add_argument('--discard-failed-worktree', action='store_true')
    ap.add_argument('--ephemeral', action='store_true')
    ap.add_argument('--json-events', action='store_true')
    ap.add_argument('--skip-git-repo-check', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if not args.allowed_file:
        print('At least one --allowed-file is required for optimistic execution.', file=sys.stderr)
        return 2

    workspace = Path(args.workspace).resolve()
    if not workspace.exists():
        print(f'Missing workspace: {workspace}', file=sys.stderr)
        return 2

    repo_root = Path(git_output(['rev-parse', '--show-toplevel'], workspace)).resolve()
    base_status = run_command(['git', 'status', '--short'], repo_root)
    worktree_root = (
        Path(args.worktree_root).resolve()
        if args.worktree_root
        else repo_root / '.zoo-agent' / 'worktrees' / short_name(args.run_id, 28) / short_name(args.task_id, 36)
    )
    run_report_path = (
        repo_root / '.zoo-agent' / 'runs' / args.run_id / 'optimistic-runs' / f'{safe_name(args.task_id)}.json'
    )

    hard_risk_hits = detect_hard_risk(args.objective, args.allowed_file)
    route_decision = {
        'run_id': args.run_id,
        'task_id': args.task_id,
        'created_at': utc_now(),
        'route': 'planned_required' if hard_risk_hits and not args.allow_hard_risk else args.execution_path,
        'hard_risk_hits': hard_risk_hits,
        'fast_prompt': args.fast_prompt,
        'worktree_root': str(worktree_root),
        'base_workspace': str(repo_root),
        'base_status_short': base_status.get('stdout', ''),
        'task_context': args.task_context,
        'dry_run': args.dry_run,
    }

    if args.dry_run or route_decision['route'] == 'planned_required':
        elapsed_ms = round((time.monotonic() - wall_started) * 1000, 3)
        payload = {
            'route_decision': route_decision,
            'status': 'dry_run' if args.dry_run else 'blocked_by_hard_risk_gate',
            'recommended_next_action': 'run without --dry-run'
            if args.dry_run
            else 'use planned_worker_or_pass_--allow-hard-risk',
            'fast_path_report': fast_contract(
                pre_codex_ms=elapsed_ms,
                codex_ms=0.0,
                total_ms=elapsed_ms,
                scope_status='not_run_dry_run' if args.dry_run else 'blocked_by_hard_risk_gate',
                tests_status='not_run_dry_run' if args.dry_run else 'blocked_by_hard_risk_gate',
            ),
        }
        write_json(run_report_path, payload)
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0 if args.dry_run else 20

    attempts = []
    retry_evidence = ''
    final_policy = None
    pre_codex_ms = 0.0
    codex_ms = 0.0
    scope_status = 'not_run'
    tests_status = 'not_run'

    for attempt_no in range(1, max(args.max_retries, 0) + 2):
        attempt_task_id = args.task_id if attempt_no == 1 else f'{args.task_id}-attempt-{attempt_no}'
        attempt = {
            'attempt': attempt_no,
            'task_id': attempt_task_id,
            'started_at': utc_now(),
        }

        worktree_path, branch_name, add_result = create_worktree(
            repo_root, worktree_root, args.run_id, args.task_id, attempt_no, args.start_point
        )
        attempt['worktree'] = str(worktree_path)
        attempt['branch'] = branch_name
        attempt['worktree_add'] = add_result
        if add_result.get('returncode') != 0:
            attempt['policy'] = {
                'status': 'worktree_create_failed',
                'recommended_next_action': 'inspect_git_worktree_state',
                'retryable': False,
            }
            attempts.append(attempt)
            final_policy = attempt['policy']
            break

        task_dir = worktree_path / '.zoo-agent' / 't' / short_name(args.run_id, 18) / short_name(attempt_task_id, 24)
        pack_result = generate_task_pack(args, attempt_task_id, task_dir, worktree_path)
        attempt['task_dir'] = str(task_dir)
        attempt['task_pack'] = pack_result
        if retry_evidence and pack_result.get('returncode') == 0:
            append_retry_context(task_dir, retry_evidence)

        if pack_result.get('returncode') != 0:
            attempt['policy'] = {
                'status': 'task_pack_failed',
                'recommended_next_action': 'fix_task_pack_generation',
                'retryable': False,
            }
            attempts.append(attempt)
            final_policy = attempt['policy']
            break

        baseline = capture_task_baseline(args, attempt_task_id, worktree_path)
        attempt['task_baseline'] = baseline
        pre_codex_ms = round((time.monotonic() - wall_started) * 1000, 3)
        codex_result = run_codex_worker(args, task_dir, worktree_path)
        codex_ms = round(float(codex_result.get('elapsed_seconds') or 0.0) * 1000, 3)
        attempt['codex_worker'] = codex_result
        codex_report = parse_json_text(str(codex_result.get('stdout') or ''))
        if codex_report:
            attempt['codex_worker_report'] = codex_report
            if isinstance(codex_report.get('worker_status'), dict):
                attempt['worker_status'] = codex_report['worker_status']
            if codex_report.get('worker_status_path'):
                attempt['worker_status_path'] = codex_report.get('worker_status_path')
        test_results = run_tests(args.test_command, worktree_path, args.test_timeout_seconds)
        attempt['test_results'] = test_results
        (task_dir / 'harness-tests.json').write_text(
            json.dumps(test_results, ensure_ascii=False, indent=2), encoding='utf-8'
        )

        delta = compare_task_baseline(args, str(baseline.get('path') or ''), worktree_path, attempt_task_id)
        attempt['task_delta'] = delta
        collect, parsed = collect_result(args, attempt_task_id, task_dir, worktree_path)
        attempt['collect_result'] = collect
        attempt['collected_result'] = parsed
        scope_status = ((parsed or {}).get('scope_guard') or {}).get('status', 'not_reported')
        failed_tests = [result for result in test_results if result.get('returncode') != 0]
        tests_status = 'not_run' if not test_results else ('failed' if failed_tests else 'passed')
        policy = choose_policy(codex_result, test_results, parsed)
        attempt['policy'] = policy
        attempt['ended_at'] = utc_now()
        attempts.append(attempt)
        final_policy = policy

        if policy['status'] in {
            'merge_candidate',
            'merge_candidate_partial',
            'verification_partial',
            'escalate_scope_violation',
        }:
            if args.discard_failed_worktree and policy['status'] == 'escalate_scope_violation':
                attempt['discard_worktree'] = maybe_discard_worktree(repo_root, worktree_path, worktree_root)
            break

        if not policy.get('retryable') or attempt_no > args.max_retries:
            if args.discard_failed_worktree and policy['status'].startswith('retryable_'):
                attempt['discard_worktree'] = maybe_discard_worktree(repo_root, worktree_path, worktree_root)
            break

        retry_evidence = summarize_failure(attempt)
        if args.discard_failed_worktree:
            attempt['discard_worktree'] = maybe_discard_worktree(repo_root, worktree_path, worktree_root)

    summary = {
        'route_decision': route_decision,
        'status': final_policy['status'] if final_policy else 'unknown',
        'recommended_next_action': final_policy['recommended_next_action'] if final_policy else 'inspect_run_report',
        'attempts': attempts,
        'ended_at': utc_now(),
        'fast_path_report': fast_contract(
            pre_codex_ms=pre_codex_ms,
            codex_ms=codex_ms,
            total_ms=round((time.monotonic() - wall_started) * 1000, 3),
            scope_status=scope_status,
            tests_status=tests_status,
        ),
    }
    write_json(run_report_path, summary)
    print(json.dumps(summary, ensure_ascii=True, indent=2))

    if summary['status'] in {'merge_candidate', 'merge_candidate_partial'}:
        return 0
    if summary['status'] == 'verification_partial':
        return 6
    if summary['status'] == 'escalate_scope_violation':
        return 30
    return 10


if __name__ == '__main__':
    raise SystemExit(main())
