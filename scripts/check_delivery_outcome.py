#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, safe_name, utc_now, write_json  # noqa: E402
from classify_codex_failure import classify as classify_codex_failure  # noqa: E402


RUNTIME_PATTERNS = [
    '.zoo-agent/**',
    '.tmp/**',
]

GOVERNANCE_PATTERNS = [
    'AGENTS.md',
    'AGENTS.md.new',
    '.gitignore.agent.patch',
    '.roo/rules/**',
    '.roo/rules.new/**',
    'bootstrap-report.md',
    'project-profile.json',
    'project-readiness.json',
]

IGNORED_GENERATED_PATTERNS = [
    '__pycache__/**',
    '**/__pycache__/**',
    '.pytest_cache/**',
    '**/.pytest_cache/**',
    '*.pyc',
    '**/*.pyc',
]

CODE_PATTERNS = [
    '*.py',
    '*.js',
    '*.jsx',
    '*.ts',
    '*.tsx',
    '*.go',
    '*.rs',
    '*.java',
    '*.cs',
    '*.cpp',
    '*.c',
    '*.h',
    '*.hpp',
    'src/**',
    'app/**',
    'lib/**',
    'backend/**',
    'frontend/**',
]

TEST_PATTERNS = [
    'tests/**',
    'test/**',
    'spec/**',
    '**/*test*',
    '**/*spec*',
]

DOC_PATTERNS = [
    'README*',
    '*.md',
    'docs/**',
    'doc/**',
]

CODING_TERMS = {
    'implement',
    'code',
    'bug',
    'validation',
    'form',
    'api',
    'schema',
    'database',
    'test',
    'function',
    'fix login',
}

DOC_TERMS = {'readme', 'doc', 'docs', 'documentation', 'typo', 'markdown'}

WORKER_BLOCKED_STATUSES = {'timeout', 'no_output_timeout', 'spawn_failed', 'exception'}
WORKER_FAILED_STATUSES = {'failed'}

NO_OP_PHRASES = [
    'no change needed',
    'no changes needed',
    'nothing to change',
    'no modification needed',
    'already correct',
    'already up to date',
    'no typo found',
    'no typos found',
    'did not find',
    '无需修改',
    '没有需要修改',
    '未发现',
]

EVIDENCE_TERMS = [
    'checked',
    'inspected',
    'reviewed',
    'verified',
    'looked at',
    'readme',
    'docs/',
    '.md',
    '检查',
    '查看',
    '验证',
]


def run_git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        ['git', *args],
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout if proc.returncode == 0 else ''


def changed_files_from_status(status: str) -> list[str]:
    files: list[str] = []
    for line in status.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if ' -> ' in path:
            path = path.split(' -> ', 1)[1]
        path = path.strip('"').replace('\\', '/')
        if path:
            files.append(path)
    return files


def git_changed_files(project: Path) -> list[str]:
    files = set()
    for command in [['diff', '--name-only'], ['diff', '--cached', '--name-only']]:
        for line in run_git(command, project).splitlines():
            if line.strip():
                files.add(line.strip().replace('\\', '/'))
    status = run_git(['status', '--porcelain=v1', '-uall'], project)
    files.update(changed_files_from_status(status))
    return sorted(files)


def matches_any(path: str, patterns: list[str]) -> bool:
    normalized = path.replace('\\', '/')
    return any(fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch('/' + normalized, pattern) for pattern in patterns)


def split_changed_files(files: list[str]) -> tuple[list[str], list[str], list[str], list[str]]:
    business: list[str] = []
    runtime: list[str] = []
    governance: list[str] = []
    ignored: list[str] = []
    for item in sorted(set(file.replace('\\', '/') for file in files if file)):
        if matches_any(item, RUNTIME_PATTERNS):
            runtime.append(item)
        elif matches_any(item, IGNORED_GENERATED_PATTERNS):
            ignored.append(item)
        elif matches_any(item, GOVERNANCE_PATTERNS):
            governance.append(item)
        else:
            business.append(item)
    return business, runtime, governance, ignored


def load_cli_report(run_dir: Path, task_id: str) -> dict[str, Any]:
    path = run_dir / 'cli-runtime' / f'{safe_name(task_id)}.json'
    if path.exists():
        payload = load_json(path)
        if payload:
            payload['_path'] = str(path)
            return payload
    reports = sorted((run_dir / 'cli-runtime').glob('*.json'))
    if len(reports) == 1:
        payload = load_json(reports[0])
        payload['_path'] = str(reports[0])
        return payload
    return {}


def parse_json_text(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def latest_attempt(run_dir: Path, task_id: str) -> dict[str, Any]:
    candidates = [run_dir / 'optimistic-runs' / f'{safe_name(task_id)}.json']
    candidates.extend(sorted((run_dir / 'optimistic-runs').glob('*.json')))
    for path in candidates:
        payload = load_json(path)
        attempts = payload.get('attempts') if isinstance(payload.get('attempts'), list) else []
        if attempts:
            attempt = attempts[-1]
            if isinstance(attempt, dict):
                attempt['_optimistic_report'] = str(path)
                attempt['_optimistic_status'] = payload.get('status', '')
                attempt['_recommended_next_action'] = payload.get('recommended_next_action', '')
                return attempt
    return {}


def nested_get(mapping: dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def existing_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    try:
        path = path.resolve()
    except OSError:
        return None
    return path if path.exists() else None


def discover_baseline_path(args: argparse.Namespace, project: Path, run_dir: Path, attempt: dict[str, Any]) -> Path | None:
    explicit = existing_path(args.baseline)
    if explicit:
        return explicit
    candidates = [
        run_dir / 'tasks' / safe_name(args.task_id) / 'task-baseline.json',
        run_dir / f'task-baseline-{safe_name(args.task_id)}.json',
        existing_path(nested_get(attempt, 'task_baseline', 'path')),
        existing_path(nested_get(attempt, 'collected_result', 'task_baseline', 'path')),
        existing_path(nested_get(attempt, 'collected_result', 'task_baseline_path')),
    ]
    for candidate in candidates:
        if isinstance(candidate, Path) and candidate.exists():
            return candidate
    for root in [
        project / '.zoo-agent' / 'worktrees' / safe_name(args.run_id) / safe_name(args.task_id),
        project / '.zoo-agent' / 'runs' / args.run_id,
    ]:
        if root.exists():
            matches = sorted(root.glob(f'**/tasks/{safe_name(args.task_id)}/task-baseline.json'))
            if matches:
                return matches[-1].resolve()
    return None


def discover_delta_path(args: argparse.Namespace, project: Path, run_dir: Path, attempt: dict[str, Any]) -> Path | None:
    explicit = existing_path(args.task_delta)
    if explicit:
        return explicit
    candidates = [
        run_dir / 'tasks' / safe_name(args.task_id) / 'task-delta.json',
        run_dir / f'task-delta-{safe_name(args.task_id)}.json',
        existing_path(nested_get(attempt, 'task_delta', 'path')),
        existing_path(nested_get(attempt, 'collected_result', 'task_delta', 'path')),
        existing_path(nested_get(attempt, 'collected_result', 'task_delta_path')),
    ]
    for candidate in candidates:
        if isinstance(candidate, Path) and candidate.exists():
            return candidate
    for root in [
        project / '.zoo-agent' / 'worktrees' / safe_name(args.run_id) / safe_name(args.task_id),
        project / '.zoo-agent' / 'runs' / args.run_id,
    ]:
        if root.exists():
            matches = sorted(root.glob(f'**/tasks/{safe_name(args.task_id)}/task-delta.json'))
            if matches:
                return matches[-1].resolve()
    return None


def compare_from_baseline(baseline_path: Path, denied_files: list[str]) -> tuple[Path | None, dict[str, Any]]:
    baseline = load_json(baseline_path)
    workspace = str(baseline.get('workspace') or '')
    if not workspace:
        return None, {'returncode': 2, 'stderr': 'baseline missing workspace'}
    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'compare_task_baseline.py'),
        '--baseline',
        str(baseline_path),
        '--workspace',
        workspace,
    ]
    for item in denied_files:
        command.extend(['--denied-file', item])
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = parse_json_text(proc.stdout)
    delta_path = existing_path(payload.get('path'))
    return delta_path, {
        'command': command,
        'returncode': proc.returncode,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def codex_returncode(attempt: dict[str, Any], cli_report: dict[str, Any]) -> int | None:
    worker_status, _ = worker_status_from_attempt(attempt)
    codex = attempt.get('codex_worker') if isinstance(attempt.get('codex_worker'), dict) else {}
    stdout_payload = parse_json_text(str(codex.get('stdout') or ''))
    for value in [
        worker_status.get('returncode'),
        stdout_payload.get('returncode'),
        codex.get('returncode'),
        (cli_report.get('execution') or {}).get('returncode') if isinstance(cli_report.get('execution'), dict) else None,
    ]:
        if isinstance(value, int):
            return value
    return None


def codex_timed_out(attempt: dict[str, Any]) -> bool:
    worker_status, _ = worker_status_from_attempt(attempt)
    if str(worker_status.get('status') or '') in {'timeout', 'no_output_timeout'}:
        return True
    codex = attempt.get('codex_worker') if isinstance(attempt.get('codex_worker'), dict) else {}
    stdout_payload = parse_json_text(str(codex.get('stdout') or ''))
    return bool(stdout_payload.get('timed_out') or codex.get('timed_out'))


def worker_status_from_attempt(attempt: dict[str, Any]) -> tuple[dict[str, Any], str]:
    candidates: list[Any] = [
        attempt.get('worker_status'),
        nested_get(attempt, 'codex_worker_report', 'worker_status'),
        nested_get(attempt, 'collected_result', 'worker_status'),
    ]
    codex = attempt.get('codex_worker') if isinstance(attempt.get('codex_worker'), dict) else {}
    stdout_payload = parse_json_text(str(codex.get('stdout') or ''))
    candidates.append(stdout_payload.get('worker_status'))

    path_candidates: list[Any] = [
        attempt.get('worker_status_path'),
        nested_get(attempt, 'codex_worker_report', 'worker_status_path'),
        nested_get(attempt, 'collected_result', 'worker_status_path'),
        stdout_payload.get('worker_status_path'),
    ]
    for path_value in path_candidates:
        path = existing_path(path_value)
        if path:
            loaded = load_json(path)
            if loaded:
                candidates.insert(0, loaded)
                for candidate in candidates:
                    if isinstance(candidate, dict) and candidate:
                        return candidate, str(path)

    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            return candidate, ''
    return {}, ''


def infer_task_type(text: str, allowed_files: list[str], business_files: list[str], explicit: str = '') -> str:
    if explicit:
        return explicit
    surface = ' '.join([text, *allowed_files, *business_files]).lower()
    if any(term in surface for term in DOC_TERMS) or (business_files and all(matches_any(path, DOC_PATTERNS) for path in business_files)):
        return 'docs'
    if any(term in surface for term in CODING_TERMS) or any(matches_any(path, CODE_PATTERNS + TEST_PATTERNS) for path in [*allowed_files, *business_files]):
        return 'coding'
    return 'edit'


def no_op_has_evidence(text: str) -> bool:
    lowered = text.lower()
    if len(lowered.strip()) < 60:
        return False
    has_reason = any(phrase in lowered for phrase in NO_OP_PHRASES)
    has_evidence = any(term in lowered for term in EVIDENCE_TERMS)
    has_file_reference = bool(re.search(r'([A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+|README|docs?/', text, re.IGNORECASE))
    return has_reason and has_evidence and has_file_reference


def tests_status_from_attempt(attempt: dict[str, Any], cli_report: dict[str, Any], task_type: str) -> str:
    if isinstance(cli_report.get('tests_status'), str) and cli_report.get('tests_status'):
        status = str(cli_report['tests_status'])
        if status not in {'passed_or_not_reported', 'failed_or_not_reported'}:
            return status
    results = attempt.get('test_results') if isinstance(attempt.get('test_results'), list) else []
    if results:
        failed = [item for item in results if isinstance(item, dict) and item.get('returncode') not in {0, None}]
        return 'failed' if failed else 'passed'
    if task_type == 'docs':
        return 'not_applicable'
    return 'not_run'


def scope_status_from_attempt(attempt: dict[str, Any], cli_report: dict[str, Any]) -> str:
    collected = attempt.get('collected_result') if isinstance(attempt.get('collected_result'), dict) else {}
    scope = collected.get('scope_guard') if isinstance(collected.get('scope_guard'), dict) else {}
    if scope.get('status'):
        return str(scope['status'])
    if cli_report.get('scope_guard_status'):
        return str(cli_report['scope_guard_status'])
    return 'not_reported'


def collected_text(attempt: dict[str, Any], run_dir: Path, task_id: str) -> str:
    parts: list[str] = []
    collected = attempt.get('collected_result') if isinstance(attempt.get('collected_result'), dict) else {}
    for key in ['final_message', 'progress_md', 'blockers_md']:
        value = collected.get(key)
        if isinstance(value, str):
            parts.append(value)
    result_dir = run_dir / 'codex-results' / task_id
    for name in ['result.md', 'result.json']:
        path = result_dir / name
        if path.exists():
            parts.append(path.read_text(encoding='utf-8', errors='replace'))
    return '\n\n'.join(parts)


def denied_hits(files: list[str], denied_files: list[str]) -> list[str]:
    return [path for path in files if matches_any(path, denied_files)]


def code_or_test_diff(files: list[str]) -> bool:
    return any(matches_any(path, CODE_PATTERNS + TEST_PATTERNS) for path in files)


def docs_diff(files: list[str]) -> bool:
    return any(matches_any(path, DOC_PATTERNS) for path in files)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"# Delivery Outcome: {payload['run_id']} / {payload['task_id']}",
        '',
        f"- route: {payload['route']}",
        f"- task_type: {payload['task_type']}",
        f"- delivery_outcome: {payload['delivery_outcome']}",
        f"- reason: {payload['reason']}",
        f"- next_action: {payload['next_action']}",
        '',
        '## Business Changed Files',
        '',
    ]
    if payload['business_changed_files']:
        lines.extend(f"- {item}" for item in payload['business_changed_files'])
    else:
        lines.append('- none')
    lines.extend(['', '## Runtime Changed Files', ''])
    if payload['runtime_changed_files']:
        lines.extend(f"- {item}" for item in payload['runtime_changed_files'])
    else:
        lines.append('- none')
    lines.extend(['', '## Governance Changed Files', ''])
    if payload.get('governance_changed_files'):
        lines.extend(f"- {item}" for item in payload['governance_changed_files'])
    else:
        lines.append('- none')
    lines.extend(['', '## Unchanged Existing Diff', ''])
    if payload.get('unchanged_existing_diff'):
        lines.extend(f"- {item}" for item in payload['unchanged_existing_diff'])
    else:
        lines.append('- none')
    lines.extend(
        [
            '',
            '## Baseline',
            '',
            f"- baseline_used: {payload.get('baseline_used')}",
            f"- baseline_path: {payload.get('baseline_path') or ''}",
            f"- task_delta_path: {payload.get('task_delta_path') or ''}",
            f"- legacy_diff_mode: {payload.get('legacy_diff_mode')}",
        ]
    )
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def evaluate(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    project = project_root(args.workspace)
    run_dir = project / '.zoo-agent' / 'runs' / args.run_id
    cli_report = load_cli_report(run_dir, args.task_id)
    attempt = latest_attempt(run_dir, args.task_id)
    collected = attempt.get('collected_result') if isinstance(attempt.get('collected_result'), dict) else {}

    route = args.route or str(cli_report.get('route') or cli_report.get('selected_path') or '')
    task_text = args.input_text or str(cli_report.get('input') or '')
    classification = cli_report.get('classification') if isinstance(cli_report.get('classification'), dict) else {}
    allowed_files = [str(item) for item in classification.get('allowed_files') or []]
    denied_files = [str(item) for item in classification.get('denied_files') or []]
    denied_files.extend(args.denied_file or [])
    baseline_path = discover_baseline_path(args, project, run_dir, attempt)
    delta_path = discover_delta_path(args, project, run_dir, attempt)
    compare_run: dict[str, Any] = {}
    if not delta_path and baseline_path:
        delta_path, compare_run = compare_from_baseline(baseline_path, denied_files)

    baseline_used = bool(baseline_path)
    legacy_diff_mode = False
    missing_task_baseline = False
    delta: dict[str, Any] = load_json(delta_path) if delta_path else {}

    if delta:
        business_files = [str(item) for item in delta.get('business_candidate_files') or []]
        runtime_files = [str(item) for item in delta.get('runtime_artifacts') or []]
        governance_files = [str(item) for item in delta.get('governance_artifacts') or []]
        ignored_files = [str(item) for item in delta.get('ignored_generated_files') or []]
        unchanged_existing_diff = [str(item) for item in delta.get('unchanged_existing_diff') or []]
        denied = [str(item) for item in delta.get('denied_files_touched') or []]
    else:
        changed = git_changed_files(project)
        changed.extend(args.changed_file or [])
        changed.extend(str(item) for item in collected.get('git_diff_name_only') or [] if item)
        business_files, runtime_files, governance_files, ignored_files = split_changed_files(changed)
        unchanged_existing_diff = []
        denied = denied_hits(business_files + governance_files, denied_files)
        actual_fast_run = bool(attempt) or bool(collected) or bool((run_dir / 'codex-results' / args.task_id).exists())
        legacy_allowed = args.allow_legacy_diff or str(cli_report.get('generated_by') or '').startswith('test_')
        if route == 'fast' and actual_fast_run and not legacy_allowed:
            missing_task_baseline = True
        else:
            legacy_diff_mode = True

    task_type = infer_task_type(task_text, allowed_files, business_files, args.task_type)
    scope_status = args.scope_guard_status or scope_status_from_attempt(attempt, cli_report)
    tests_status = args.tests_status or tests_status_from_attempt(attempt, cli_report, task_type)
    returncode = codex_returncode(attempt, cli_report)
    timed_out = codex_timed_out(attempt)
    worker_status, worker_status_path = worker_status_from_attempt(attempt)
    worker_state = str(worker_status.get('status') or '')
    evidence_text = collected_text(attempt, run_dir, args.task_id)
    no_op_evidence = no_op_has_evidence(evidence_text)

    outcome = 'executed'
    reason = 'worker_executed_without_delivery_requirement'
    next_action = 'review_result'

    if missing_task_baseline:
        outcome = 'blocked'
        reason = 'missing_task_baseline'
        next_action = 'capture_task_baseline_before_actual_execution'
    elif denied or scope_status == 'fail':
        outcome = 'unsafe'
        reason = 'scope_guard_failed_or_denied_files_touched'
        next_action = 'stop_and_review_scope'
    elif worker_state in WORKER_BLOCKED_STATUSES:
        outcome = 'blocked'
        reason = 'worker_execution_failed'
        next_action = 'inspect_codex_worker_status_and_logs'
    elif worker_state in WORKER_FAILED_STATUSES:
        outcome = 'blocked'
        reason = 'worker_returned_nonzero'
        next_action = 'inspect_codex_worker_status_and_logs'
    elif timed_out or (returncode is not None and returncode != 0):
        outcome = 'blocked'
        reason = 'worker_failed_or_timed_out'
        next_action = 'inspect_worker_output_or_retry'
    elif not business_files:
        if task_type in {'bootstrap', 'governance'} and (governance_files or runtime_files):
            outcome = 'delivered'
            reason = 'governance_or_bootstrap_artifacts_changed'
            next_action = 'review_governance_artifacts'
        elif no_op_evidence:
            outcome = 'no_op_with_evidence'
            reason = 'no_business_diff_but_explicit_no_op_evidence_present'
            next_action = 'accept_no_op_or_clarify_task'
        elif route == 'fast' and task_type in {'coding', 'docs', 'edit'}:
            outcome = 'no_delivery'
            reason = 'fast_task_finished_without_business_diff_or_no_op_evidence'
            next_action = 'clarify_task_or_specify_file_and_change'
        else:
            outcome = 'executed'
            reason = 'no_business_diff_for_non_delivery_task'
            next_action = 'review_result'
    elif task_type == 'coding' and not code_or_test_diff(business_files):
        outcome = 'no_delivery'
        reason = 'coding_task_changed_no_code_or_test_files'
        next_action = 'schedule_implementation_pass'
    elif task_type == 'docs' and not docs_diff(business_files):
        outcome = 'no_delivery'
        reason = 'docs_task_changed_no_docs_or_readme_files'
        next_action = 'clarify_docs_target'
    elif tests_status in {'failed', 'failed_or_not_reported'}:
        outcome = 'blocked'
        reason = 'tests_failed_or_not_reported_as_failed'
        next_action = 'inspect_test_results'
    else:
        outcome = 'delivered'
        reason = 'business_diff_present_and_policy_checks_passed'
        next_action = 'review_diff_before_merge'

    payload = {
        'schema_version': '1.0',
        'generated_by': 'check_delivery_outcome.py',
        'generated_at': utc_now(),
        'run_id': args.run_id,
        'task_id': args.task_id,
        'route': route,
        'task_type': task_type,
        'baseline_used': baseline_used,
        'baseline_path': str(baseline_path or ''),
        'task_delta_path': str(delta_path or ''),
        'legacy_diff_mode': legacy_diff_mode,
        'compare_task_baseline': compare_run,
        'business_changed_files': business_files,
        'runtime_changed_files': runtime_files,
        'governance_changed_files': governance_files,
        'unchanged_existing_diff': unchanged_existing_diff,
        'ignored_generated_files': ignored_files,
        'worker_status': worker_status,
        'worker_status_path': worker_status_path,
        'worker_execution_status': worker_state,
        'codex_returncode': returncode,
        'scope_guard_status': scope_status,
        'tests_status': tests_status,
        'result_collected': bool(attempt.get('collected_result') or (run_dir / 'codex-results' / args.task_id).exists()),
        'denied_files_touched': denied,
        'no_op_evidence_present': no_op_evidence,
        'delivery_outcome': outcome,
        'reason': reason,
        'next_action': next_action,
    }
    payload['failure_classification'] = classify_codex_failure(
        text=reason,
        worker_status=worker_state,
        delivery_outcome=outcome,
        scope_guard_status=scope_status,
        returncode=returncode,
    )
    output = Path(args.output).resolve() if args.output else run_dir / 'delivery-outcome.json'
    write_json(output, payload)
    write_markdown(output.with_suffix('.md'), payload)
    return 0 if outcome in {'executed', 'delivered', 'no_op_with_evidence'} else 1, payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify execution versus delivery for a runtime run.')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--baseline', default='')
    parser.add_argument('--task-delta', default='')
    parser.add_argument('--route', default='')
    parser.add_argument('--task-type', choices=['coding', 'docs', 'edit', 'bootstrap', 'governance', 'research', 'analysis', 'unknown'], default='')
    parser.add_argument('--input-text', default='')
    parser.add_argument('--scope-guard-status', default='')
    parser.add_argument('--tests-status', default='')
    parser.add_argument('--changed-file', action='append', default=[])
    parser.add_argument('--denied-file', action='append', default=[])
    parser.add_argument('--allow-legacy-diff', action='store_true')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    code, payload = evaluate(args)
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
