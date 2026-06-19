#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def git_root(workspace: Path) -> Path:
    proc = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        cwd=workspace,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or 'workspace is not a git repository')
    return Path(proc.stdout.strip()).resolve()


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def refresh_summary(repo_root: Path, run_id: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'summarize_ai_native_run.py'), '--run-id', run_id, '--workspace', str(repo_root)],
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}


def blocker(blockers: list[dict], blocker_id: str, message: str, *, severity: str = 'medium', evidence: str = '') -> None:
    blockers.append({'id': blocker_id, 'severity': severity, 'message': message, 'evidence': evidence})


def warning(warnings: list[dict], warning_id: str, message: str, *, evidence: str = '') -> None:
    warnings.append({'id': warning_id, 'message': message, 'evidence': evidence})


def cli_runtime_reports(run_dir: Path) -> list[dict]:
    reports: list[dict] = []
    for path in sorted((run_dir / 'cli-runtime').glob('*.json')):
        payload = load_json(path)
        if payload:
            payload['_path'] = str(path)
            reports.append(payload)
    return reports


def is_fast_only_run(reports: list[dict]) -> bool:
    return bool(reports) and all(str(item.get('route') or item.get('selected_path') or '') == 'fast' for item in reports)


def run_fast_gate(repo_root: Path, run_id: str, task_id: str) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'check_fast_path_gate.py'),
            '--workspace',
            str(repo_root),
            '--run-id',
            run_id,
            '--task-id',
            task_id,
        ],
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = load_json(repo_root / '.zoo-agent' / 'runs' / run_id / 'fast-path-gate.json')
    payload['_command_returncode'] = proc.returncode
    payload['_stdout'] = proc.stdout
    payload['_stderr'] = proc.stderr
    return payload


def run_fast_quality_gate(repo_root: Path, run_id: str, run_dir: Path, output_path: Path, reports: list[dict]) -> int:
    blockers: list[dict] = []
    warnings: list[dict] = []
    gates: list[dict] = []
    for report in reports:
        task_id = str(report.get('task_id') or '')
        if not task_id:
            blocker(blockers, 'fast_task_id_missing', 'A fast cli-runtime report is missing task_id.', severity='high')
            continue
        gate = run_fast_gate(repo_root, run_id, task_id)
        gates.append(gate)
        if gate.get('gate_status') == 'blocked':
            blockers.extend(gate.get('blockers') or [])
        else:
            warnings.extend(gate.get('warnings') or [])

    gate_status = 'blocked' if blockers else 'pass'
    closure = {
        'execution_closure': bool(reports),
        'evidence_closure': not blockers,
        'goal_alignment_closure': True,
        'state_closure': True,
        'integration_closure': False,
    }
    payload = {
        'schema_version': '1.0',
        'generated_by': 'run_quality_gate.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'workspace': str(repo_root),
        'gate_profile': 'fast_path',
        'gate_status': gate_status,
        'closure': closure,
        'readiness_flags': {
            'merge_queue_processing_recommended': False,
            'merge_queue_processing_authorized': False,
            'approved_for_merge': False,
            'approved_for_deploy': False,
            'approved_for_release': False,
        },
        'fast_path_gates': gates,
        'blockers': blockers,
        'warnings': warnings,
        'summary_path': str(run_dir / 'ai-native-summary.json'),
        'merge_queue_path': str(run_dir / 'merge-queue.json'),
        'skipped_governed_requirements': [
            'task_board_evidence',
            'parent_aggregation',
            'implementation_queue',
            'governed_reviewer',
            'curator',
            'eval_suite',
            'release_readiness',
            'operational_readiness',
            'full_test_matrix',
            'product_docs',
        ],
        'operator_inputs': {'fast_path_gate': True},
    }
    write_json(output_path, payload)
    write_markdown(output_path.with_suffix('.md'), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if gate_status == 'pass':
        return 0
    return 10 if gate_status == 'needs_review' else 20


def optimistic_attempts(run_dir: Path) -> list[dict]:
    attempts = []
    for path in sorted((run_dir / 'optimistic-runs').glob('*.json')):
        payload = load_json(path)
        for attempt in payload.get('attempts') or []:
            if isinstance(attempt, dict):
                attempt['_report_path'] = str(path)
                attempts.append(attempt)
    return attempts


def test_findings(run_dir: Path) -> tuple[list[dict], list[dict]]:
    failed = []
    missing = []
    for attempt in optimistic_attempts(run_dir):
        policy = attempt.get('policy') if isinstance(attempt.get('policy'), dict) else {}
        results = attempt.get('test_results') if isinstance(attempt.get('test_results'), list) else []
        if not results and policy.get('status') in {'merge_candidate', 'merge_candidate_partial'}:
            missing.append({'task_id': attempt.get('task_id', ''), 'report_path': attempt.get('_report_path', '')})
        for result in results:
            if isinstance(result, dict) and result.get('returncode') not in {0, None}:
                failed.append(
                    {
                        'task_id': attempt.get('task_id', ''),
                        'command': result.get('command', ''),
                        'returncode': result.get('returncode'),
                        'report_path': attempt.get('_report_path', ''),
                    }
                )
    return failed, missing


def goal_alignment_findings(run_dir: Path, summary: dict, merge_queue: dict) -> tuple[list[dict], list[dict], list[dict]]:
    observed: set[str] = set()
    for key in ['dispatcher_runs', 'optimistic_runs', 'codex_results', 'merge_candidates']:
        for item in summary.get(key) or []:
            if isinstance(item, dict) and item.get('task_id'):
                observed.add(str(item['task_id']))
    for item in merge_queue.get('candidates') or []:
        if isinstance(item, dict) and item.get('task_id'):
            observed.add(str(item['task_id']))

    reports: dict[str, dict] = {}
    for path in sorted((run_dir / 'goal-alignment').glob('*.json')):
        payload = load_json(path)
        task_id = str(payload.get('task_id') or path.stem)
        if task_id:
            payload['_path'] = str(path)
            reports[task_id] = payload

    missing = [{'task_id': task_id} for task_id in sorted(observed) if task_id not in reports]
    blocked = [
        {
            'task_id': task_id,
            'status': payload.get('status', 'unknown'),
            'path': payload.get('_path', ''),
            'blockers': payload.get('blockers') or [],
        }
        for task_id, payload in sorted(reports.items())
        if payload.get('status') == 'blocked'
    ]
    needs_review = [
        {
            'task_id': task_id,
            'status': payload.get('status', 'unknown'),
            'path': payload.get('_path', ''),
            'warnings': payload.get('warnings') or [],
        }
        for task_id, payload in sorted(reports.items())
        if payload.get('status') == 'needs_review'
    ]
    return missing, blocked, needs_review


def parent_aggregation_requires_review(parent: dict) -> bool:
    if not parent:
        return False
    next_phase = parent.get('next_phase_decision') if isinstance(parent.get('next_phase_decision'), dict) else {}
    status = str(next_phase.get('status') or parent.get('status') or '').lower()
    return status in {'review_required', 'parallel_leaf_results_recorded'}


def write_markdown(path: Path, payload: dict) -> None:
    lines = [
        f"# Quality Gate: {payload['run_id']}",
        '',
        f"- status: {payload['gate_status']}",
        f"- execution_closure: {payload['closure']['execution_closure']}",
        f"- evidence_closure: {payload['closure']['evidence_closure']}",
        f"- goal_alignment_closure: {payload['closure']['goal_alignment_closure']}",
        f"- state_closure: {payload['closure']['state_closure']}",
        f"- integration_closure: {payload['closure']['integration_closure']}",
        f"- merge_queue_processing_authorized: {payload['readiness_flags']['merge_queue_processing_authorized']}",
        '',
        '## Blockers',
        '',
    ]
    if not payload['blockers']:
        lines.append('- none')
    else:
        for item in payload['blockers']:
            lines.append(f"- {item.get('id')}: {item.get('message')}")
    lines += ['', '## Warnings', '']
    if not payload['warnings']:
        lines.append('- none')
    else:
        for item in payload['warnings']:
            lines.append(f"- {item.get('id')}: {item.get('message')}")
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser(description='Run the Zoo evidence quality gate for a run.')
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--output', default='')
    ap.add_argument('--no-refresh-summary', action='store_true')
    ap.add_argument('--governance-only', action='store_true')
    ap.add_argument('--allow-missing-tests', action='store_true')
    ap.add_argument('--allow-missing-goal-alignment', action='store_true')
    ap.add_argument('--allow-open-risks', action='store_true')
    ap.add_argument('--allow-task-board-warnings', action='store_true')
    ap.add_argument('--allow-project-readiness-blocks', action='store_true')
    ap.add_argument('--allow-architecture-blocks', action='store_true')
    ap.add_argument('--accept-parent-aggregation', action='store_true')
    ap.add_argument('--authorize-merge-queue', action='store_true')
    args = ap.parse_args()

    repo_root = git_root(Path(args.workspace).resolve())
    run_dir = repo_root / '.zoo-agent' / 'runs' / args.run_id
    output_path = Path(args.output).resolve() if args.output else run_dir / 'quality-gate.json'
    reports = cli_runtime_reports(run_dir)
    if is_fast_only_run(reports):
        return run_fast_quality_gate(repo_root, args.run_id, run_dir, output_path, reports)

    refresh = {'skipped': True}
    if not args.no_refresh_summary:
        refresh = refresh_summary(repo_root, args.run_id)

    summary = load_json(run_dir / 'ai-native-summary.json')
    governance = summary.get('governance_state') if isinstance(summary.get('governance_state'), dict) else {}
    totals = summary.get('totals') if isinstance(summary.get('totals'), dict) else {}
    readiness = governance.get('project_readiness') if isinstance(governance.get('project_readiness'), dict) else {}
    merge_queue = load_json(run_dir / 'merge-queue.json')
    parent_aggregation = load_json(run_dir / 'parent-aggregation.json')
    risk_register = load_json(run_dir / 'risk-register.json')
    task_board = load_json(run_dir / 'task-board-consistency.json')
    architecture = load_json(repo_root / '.zoo-agent' / 'architecture-compatibility-report.json')

    blockers: list[dict] = []
    warnings: list[dict] = []

    worker_count = int(totals.get('optimistic_runs') or 0) + int(totals.get('codex_results') or 0)
    if worker_count == 0 and not args.governance_only:
        blocker(blockers, 'execution_closure_missing', 'No worker/result evidence was found and the run is not marked governance-only.', severity='high')

    if readiness.get('blocking_issues') and not args.allow_project_readiness_blocks:
        blocker(
            blockers,
            'project_readiness_blocking_issues',
            'Project readiness has blocking issues.',
            severity='high',
            evidence=', '.join(str(item) for item in readiness.get('blocking_issues') or []),
        )

    arch_status = str(architecture.get('status') or 'missing')
    if arch_status == 'blocked' and not args.allow_architecture_blocks:
        blocker(blockers, 'architecture_compatibility_blocked', 'Architecture compatibility report is blocked.', severity='high')
    elif arch_status == 'needs_review':
        warning(warnings, 'architecture_compatibility_needs_review', 'Architecture compatibility report needs review.')

    bad_scope = []
    for result in summary.get('codex_results') or []:
        if isinstance(result, dict) and result.get('scope_status') != 'pass':
            bad_scope.append(result)
    for run in summary.get('optimistic_runs') or []:
        if isinstance(run, dict) and run.get('status') in {'merge_candidate', 'merge_candidate_partial'} and run.get('scope_status') != 'pass':
            bad_scope.append(run)
    if bad_scope:
        blocker(blockers, 'scope_guard_not_passing', 'One or more candidate results lack a passing scope guard.', severity='high', evidence=json.dumps(bad_scope[:5], ensure_ascii=False))

    failed_tests, missing_tests = test_findings(run_dir)
    if failed_tests:
        blocker(blockers, 'tests_failed', 'One or more harness test commands failed.', severity='high', evidence=json.dumps(failed_tests[:5], ensure_ascii=False))
    if missing_tests and not args.allow_missing_tests:
        blocker(blockers, 'tests_missing_for_candidate', 'Merge candidates exist without recorded harness tests.', severity='medium', evidence=json.dumps(missing_tests[:5], ensure_ascii=False))
    elif missing_tests:
        warning(warnings, 'tests_missing_allowed', 'Merge candidates exist without recorded harness tests, but this was allowed.')

    missing_alignment, blocked_alignment, review_alignment = goal_alignment_findings(run_dir, summary, merge_queue)
    if missing_alignment and not args.allow_missing_goal_alignment:
        blocker(
            blockers,
            'goal_alignment_missing',
            'One or more observed tasks are missing goal-alignment evidence.',
            severity='high',
            evidence=json.dumps(missing_alignment[:10], ensure_ascii=False),
        )
    elif missing_alignment:
        warning(warnings, 'goal_alignment_missing_allowed', 'Observed tasks are missing goal-alignment evidence, but this was allowed.')
    if blocked_alignment:
        blocker(
            blockers,
            'goal_alignment_blocked',
            'One or more goal-alignment checks are blocked.',
            severity='high',
            evidence=json.dumps(blocked_alignment[:10], ensure_ascii=False),
        )
    if review_alignment:
        warning(
            warnings,
            'goal_alignment_needs_review',
            'One or more goal-alignment checks need review.',
            evidence=json.dumps(review_alignment[:10], ensure_ascii=False),
        )

    open_risk_count = int(risk_register.get('open_risk_count') or 0)
    if open_risk_count and not args.allow_open_risks:
        blocker(blockers, 'open_run_risks', 'Open run-level risks remain.', severity='high', evidence=str(open_risk_count))
    elif open_risk_count:
        warning(warnings, 'open_run_risks_allowed', 'Open run-level risks remain, but this was allowed.')

    if task_board.get('status') == 'warnings' and not args.allow_task_board_warnings:
        blocker(blockers, 'task_board_consistency_warnings', 'Task-board consistency warnings remain.', severity='medium')
    elif task_board.get('status') == 'warnings':
        warning(warnings, 'task_board_consistency_warnings_allowed', 'Task-board consistency warnings remain, but this was allowed.')

    if parent_aggregation_requires_review(parent_aggregation) and not args.accept_parent_aggregation:
        blocker(blockers, 'parent_aggregation_review_required', 'Parent aggregation requires review before queue processing.', severity='medium')
    elif parent_aggregation_requires_review(parent_aggregation):
        warning(warnings, 'parent_aggregation_accepted', 'Parent aggregation review requirement was explicitly accepted.')

    candidate_count = len(merge_queue.get('candidates') or []) if isinstance(merge_queue.get('candidates'), list) else int(totals.get('merge_candidates') or 0)
    if candidate_count and not merge_queue:
        warning(warnings, 'merge_queue_missing', 'Merge candidates exist but merge-queue.json is missing.')

    gate_status = 'blocked' if blockers else ('needs_review' if warnings else 'pass')
    can_authorize_queue = gate_status == 'pass' and args.authorize_merge_queue
    merge_queue_flags = merge_queue.get('readiness_flags') if isinstance(merge_queue.get('readiness_flags'), dict) else {}
    closure = {
        'execution_closure': worker_count > 0 or args.governance_only,
        'evidence_closure': not any(item['id'] in {'scope_guard_not_passing', 'tests_failed', 'tests_missing_for_candidate'} for item in blockers),
        'goal_alignment_closure': not any(item['id'] in {'goal_alignment_missing', 'goal_alignment_blocked'} for item in blockers),
        'state_closure': not any(item['id'] in {'open_run_risks', 'task_board_consistency_warnings'} for item in blockers),
        'integration_closure': bool(
            merge_queue_flags.get('merge_queue_processing_authorized')
            and merge_queue.get('queue_status') not in {'record_only_parallel_candidates_not_processable', 'missing', ''}
        ),
    }
    readiness_flags = {
        'merge_queue_processing_recommended': gate_status == 'pass',
        'merge_queue_processing_authorized': can_authorize_queue,
        'approved_for_merge': False,
        'approved_for_deploy': False,
        'approved_for_release': False,
    }
    payload = {
        'schema_version': '1.0',
        'generated_by': 'run_quality_gate.py',
        'generated_at': utc_now(),
        'run_id': args.run_id,
        'workspace': str(repo_root),
        'gate_status': gate_status,
        'closure': closure,
        'readiness_flags': readiness_flags,
        'blockers': blockers,
        'warnings': warnings,
        'summary_path': str(run_dir / 'ai-native-summary.json'),
        'merge_queue_path': str(run_dir / 'merge-queue.json'),
        'refresh_summary': refresh,
        'operator_inputs': {
            'governance_only': args.governance_only,
            'allow_missing_tests': args.allow_missing_tests,
            'allow_missing_goal_alignment': args.allow_missing_goal_alignment,
            'allow_open_risks': args.allow_open_risks,
            'allow_task_board_warnings': args.allow_task_board_warnings,
            'allow_project_readiness_blocks': args.allow_project_readiness_blocks,
            'allow_architecture_blocks': args.allow_architecture_blocks,
            'accept_parent_aggregation': args.accept_parent_aggregation,
            'authorize_merge_queue': args.authorize_merge_queue,
        },
    }
    write_json(output_path, payload)
    write_markdown(output_path.with_suffix('.md'), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if gate_status == 'pass':
        return 0
    return 10 if gate_status == 'needs_review' else 20


if __name__ == '__main__':
    raise SystemExit(main())
