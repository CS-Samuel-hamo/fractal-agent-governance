#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import subprocess
from pathlib import Path


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


def load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def last_attempt(report: dict) -> dict:
    attempts = report.get('attempts') or []
    if not attempts:
        return {}
    return attempts[-1] if isinstance(attempts[-1], dict) else {}


def collect_dispatcher_runs(run_dir: Path) -> list[dict]:
    rows = []
    for path in sorted((run_dir / 'dispatcher-runs').glob('*.json')):
        payload = load_json(path)
        if not payload:
            continue
        selection = payload.get('selection') or {}
        graph = selection.get('execution_graph') or {}
        parallel = graph.get('parallel_contract') or {}
        rollback = graph.get('rollback_contract') or {}
        rows.append(
            {
                'task_id': selection.get('task_id') or path.stem,
                'source': 'dispatcher',
                'status': payload.get('status', 'unknown'),
                'recommended_path': selection.get('recommended_path', 'unknown'),
                'reason': selection.get('reason', ''),
                'chain_weight': graph.get('chain_weight', 'unknown'),
                'misroute_risk': graph.get('misroute_risk', 'unknown'),
                'judgment_node_count': graph.get('judgment_node_count', 0),
                'parallelizable': bool(parallel.get('parallelizable')),
                'conflict_keys': parallel.get('conflict_keys') or [],
                'rollback_mode': rollback.get('mode', 'unknown'),
                'report_path': str(path),
            }
        )
    return rows


def collect_optimistic_runs(run_dir: Path) -> tuple[list[dict], list[dict]]:
    rows = []
    merge_candidates = []
    for path in sorted((run_dir / 'optimistic-runs').glob('*.json')):
        payload = load_json(path)
        if not payload:
            continue
        route = payload.get('route_decision') or {}
        attempt = last_attempt(payload)
        collected = attempt.get('collected_result') or {}
        changed_files = collected.get('git_diff_name_only') or []
        row = {
            'task_id': route.get('task_id') or path.stem,
            'source': 'optimistic',
            'status': payload.get('status', 'unknown'),
            'recommended_path': route.get('route', 'unknown'),
            'attempt_count': len(payload.get('attempts') or []),
            'worktree': attempt.get('worktree', ''),
            'branch': attempt.get('branch', ''),
            'scope_status': (collected.get('scope_guard') or {}).get('status', 'unknown'),
            'changed_files': changed_files,
            'report_path': str(path),
        }
        rows.append(row)
        if row['status'] in {'merge_candidate', 'merge_candidate_partial'}:
            merge_candidates.append(
                {
                    'task_id': row['task_id'],
                    'status': row['status'],
                    'worktree': row['worktree'],
                    'branch': row['branch'],
                    'changed_files': changed_files,
                    'report_path': str(path),
                }
            )
    return rows, merge_candidates


def collect_codex_results(run_dir: Path) -> list[dict]:
    rows = []
    for path in sorted((run_dir / 'codex-results').glob('*/result.json')):
        payload = load_json(path)
        if not payload:
            continue
        rows.append(
            {
                'task_id': payload.get('task_id') or path.parent.name,
                'source': 'codex_result',
                'scope_status': (payload.get('scope_guard') or {}).get('status', 'unknown'),
                'changed_files': payload.get('git_diff_name_only') or [],
                'report_path': str(path),
            }
        )
    return rows


def collect_fractal_workstreams(run_dir: Path) -> list[dict]:
    rows = []
    for path in sorted((run_dir / 'fractal-workstreams').glob('*.json')):
        payload = load_json(path)
        if not payload:
            continue
        selection = payload.get('selection') or {}
        graph = selection.get('execution_graph') or {}
        parallel = graph.get('parallel_contract') or {}
        rollback = graph.get('rollback_contract') or {}
        rows.append(
            {
                'task_id': payload.get('task_id') or path.stem,
                'source': 'fractal_workstream',
                'status': payload.get('status', 'unknown'),
                'parent_task_pack': payload.get('parent_task_pack', ''),
                'leaf_skeleton_count': ((payload.get('leaf_skeletons') or {}).get('leaf_count') or 0),
                'leaf_skeleton_index': ((payload.get('leaf_skeletons') or {}).get('index') or ''),
                'chain_weight': graph.get('chain_weight', 'unknown'),
                'misroute_risk': graph.get('misroute_risk', 'unknown'),
                'parallelizable': bool(parallel.get('parallelizable')),
                'conflict_keys': parallel.get('conflict_keys') or [],
                'rollback_mode': rollback.get('mode', 'unknown'),
                'report_path': str(path),
            }
        )
    return rows


def collect_governance_state(repo_root: Path, run_dir: Path) -> dict:
    status = load_json(run_dir / 'status.json') or {}
    current_run = load_json(repo_root / '.zoo-agent' / 'current-run.json') or {}
    merge_queue = load_json(run_dir / 'merge-queue.json') or {}
    parent_aggregation = load_json(run_dir / 'parent-aggregation.json') or {}
    risk_register = load_json(run_dir / 'risk-register.json') or {}
    quality_gate = load_json(run_dir / 'quality-gate.json') or {}
    resource_locks = load_json(repo_root / '.zoo-agent' / 'locks' / 'resource-locks.json') or {}
    project_readiness = load_json(repo_root / '.zoo-agent' / 'project-readiness.json') or {}
    task_board_consistency = load_json(run_dir / 'task-board-consistency.json') or {}

    risks = risk_register.get('risks') if isinstance(risk_register.get('risks'), list) else []
    open_risks = [
        {
            'risk_id': risk.get('risk_id') or risk.get('id') or '',
            'title': risk.get('title') or '',
            'severity': risk.get('severity') or '',
            'status': risk.get('status') or '',
        }
        for risk in risks
        if isinstance(risk, dict) and 'closed' not in str(risk.get('status') or '').lower()
    ]

    readiness_flags = merge_queue.get('readiness_flags') if isinstance(merge_queue.get('readiness_flags'), dict) else {}
    queue_status = merge_queue.get('queue_status') or merge_queue.get('gate_status') or 'missing'
    final_parent = parent_aggregation.get('final_parent_aggregation')
    if not isinstance(final_parent, dict):
        final_parent = {}
    parent_status = (
        parent_aggregation.get('gate_status')
        or final_parent.get('status')
        or parent_aggregation.get('status')
        or 'missing'
    )
    return {
        'project_readiness': {
            'codex_cli_ready': project_readiness.get('codex_cli_ready', 'unknown'),
            'safe_for_level_0_1_trial': project_readiness.get('safe_for_level_0_1_trial', 'unknown'),
            'blocking_issues': project_readiness.get('blocking_issues') or [],
        },
        'run_status': {
            'gate_status': status.get('gate_status', 'missing'),
            'current_state': status.get('current_state') or current_run.get('current_state') or 'unknown',
            'active_branch': status.get('active_branch') or current_run.get('active_branch') or 'unknown',
            'next_recommended_phase': status.get('next_recommended_phase')
            or current_run.get('next_recommended_phase')
            or 'unknown',
            'business_code_modified': status.get('business_code_modified', 'unknown'),
        },
        'merge_queue': {
            'queue_status': queue_status,
            'approved_for_merge': readiness_flags.get('approved_for_merge', False),
            'approved_for_deploy': readiness_flags.get('approved_for_deploy', False),
            'approved_for_release': readiness_flags.get('approved_for_release', False),
            'merge_queue_processing_authorized': readiness_flags.get('merge_queue_processing_authorized', False),
            'blocker_count': len(merge_queue.get('blockers') or [])
            if isinstance(merge_queue.get('blockers'), list)
            else 0,
        },
        'parent_aggregation': {
            'status': parent_status,
            'next_phase_decision': parent_aggregation.get('next_phase_decision') or {},
        },
        'risk_register': {
            'open_risk_count': len(open_risks),
            'open_risks': open_risks[:20],
        },
        'quality_gate': {
            'gate_status': quality_gate.get('gate_status', 'missing'),
            'blocker_count': len(quality_gate.get('blockers') or [])
            if isinstance(quality_gate.get('blockers'), list)
            else 0,
            'merge_queue_processing_authorized': (
                quality_gate.get('readiness_flags', {}).get('merge_queue_processing_authorized', False)
                if isinstance(quality_gate.get('readiness_flags'), dict)
                else False
            ),
        },
        'resource_locks': {
            'active_lock_count': len(resource_locks.get('locks') or [])
            if isinstance(resource_locks.get('locks'), list)
            else 0,
        },
        'task_board_consistency': {
            'status': task_board_consistency.get('status', 'missing'),
            'warnings': task_board_consistency.get('warnings') or [],
        },
    }


def write_markdown(path: Path, summary: dict) -> None:
    lines = [
        f'# AI Native Run Summary: {summary["run_id"]}',
        '',
        '## Totals',
        '',
        f'- Tasks observed: {summary["totals"]["tasks_observed"]}',
        f'- Dispatcher runs: {summary["totals"]["dispatcher_runs"]}',
        f'- Optimistic runs: {summary["totals"]["optimistic_runs"]}',
        f'- Fractal workstreams: {summary["totals"]["fractal_workstreams"]}',
        f'- Merge candidates: {summary["totals"]["merge_candidates"]}',
        '',
        '## Status Counts',
        '',
    ]
    for status, count in sorted(summary['status_counts'].items()):
        lines.append(f'- {status}: {count}')
    lines += ['', '## Path Counts', '']
    for status, count in sorted(summary['path_counts'].items()):
        lines.append(f'- {status}: {count}')
    governance = summary.get('governance_state') or {}
    readiness = governance.get('project_readiness') or {}
    run_status = governance.get('run_status') or {}
    merge_queue = governance.get('merge_queue') or {}
    risks = governance.get('risk_register') or {}
    quality_gate = governance.get('quality_gate') or {}
    resource_locks = governance.get('resource_locks') or {}
    lines += ['', '## Governance State', '']
    lines += [
        f'- codex_cli_ready: {readiness.get("codex_cli_ready", "unknown")}',
        f'- safe_for_level_0_1_trial: {readiness.get("safe_for_level_0_1_trial", "unknown")}',
        f'- current_state: {run_status.get("current_state", "unknown")}',
        f'- active_branch: {run_status.get("active_branch", "unknown")}',
        f'- next_recommended_phase: {run_status.get("next_recommended_phase", "unknown")}',
        f'- merge_queue_status: {merge_queue.get("queue_status", "unknown")}',
        f'- approved_for_merge: {merge_queue.get("approved_for_merge", False)}',
        f'- merge_queue_processing_authorized: {merge_queue.get("merge_queue_processing_authorized", False)}',
        f'- open_risk_count: {risks.get("open_risk_count", 0)}',
        f'- quality_gate_status: {quality_gate.get("gate_status", "missing")}',
        f'- quality_gate_blocker_count: {quality_gate.get("blocker_count", 0)}',
        f'- active_resource_lock_count: {resource_locks.get("active_lock_count", 0)}',
    ]
    lines += ['', '## Dispatcher Graph', '']
    if summary['dispatcher_runs']:
        for item in summary['dispatcher_runs']:
            lines.append(
                f'- {item["task_id"]}: {item["recommended_path"]}, weight={item.get("chain_weight")}, '
                f'risk={item.get("misroute_risk")}, parallel={item.get("parallelizable")}, rollback={item.get("rollback_mode")}'
            )
    else:
        lines.append('- none')
    lines += ['', '## Merge Candidates', '']
    if summary['merge_candidates']:
        for item in summary['merge_candidates']:
            lines.append(f'- {item["task_id"]} ({item["status"]}): {item["worktree"]}')
    else:
        lines.append('- none')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser(description='Summarize AI-native dispatcher, optimistic, and Codex result artifacts.')
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--output', default='')
    args = ap.parse_args()

    repo_root = git_root(Path(args.workspace).resolve())
    run_dir = repo_root / '.zoo-agent' / 'runs' / args.run_id
    summary_path = Path(args.output).resolve() if args.output else run_dir / 'ai-native-summary.json'
    md_path = summary_path.with_suffix('.md')

    dispatcher_rows = collect_dispatcher_runs(run_dir)
    optimistic_rows, merge_candidates = collect_optimistic_runs(run_dir)
    codex_rows = collect_codex_results(run_dir)
    fractal_rows = collect_fractal_workstreams(run_dir)
    governance_state = collect_governance_state(repo_root, run_dir)

    status_counts = collections.Counter()
    path_counts = collections.Counter()
    observed_tasks = set()
    for row in dispatcher_rows + optimistic_rows:
        status_counts[row.get('status', 'unknown')] += 1
        path_counts[row.get('recommended_path', 'unknown')] += 1
        observed_tasks.add(row.get('task_id', 'unknown'))
    for row in codex_rows:
        observed_tasks.add(row.get('task_id', 'unknown'))
    for row in fractal_rows:
        status_counts[row.get('status', 'unknown')] += 1
        observed_tasks.add(row.get('task_id', 'unknown'))

    summary = {
        'run_id': args.run_id,
        'workspace': str(repo_root),
        'totals': {
            'tasks_observed': len(observed_tasks),
            'dispatcher_runs': len(dispatcher_rows),
            'optimistic_runs': len(optimistic_rows),
            'fractal_workstreams': len(fractal_rows),
            'codex_results': len(codex_rows),
            'merge_candidates': len(merge_candidates),
        },
        'status_counts': dict(status_counts),
        'path_counts': dict(path_counts),
        'dispatcher_runs': dispatcher_rows,
        'optimistic_runs': optimistic_rows,
        'fractal_workstreams': fractal_rows,
        'codex_results': codex_rows,
        'merge_candidates': merge_candidates,
        'governance_state': governance_state,
    }

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    write_markdown(md_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
