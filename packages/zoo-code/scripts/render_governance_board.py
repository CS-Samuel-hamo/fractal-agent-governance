#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import datetime
import json
import re
import subprocess
from pathlib import Path
from typing import Any


CHECKBOX_RE = re.compile(r'^\s*[-*]\s+\[([ xX!\-~?])\]\s+(.*)$')


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
        return workspace.resolve()
    return Path(proc.stdout.strip()).resolve()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def read_text(path: Path, limit: int = 12000) -> str:
    try:
        text = path.read_text(encoding='utf-8-sig', errors='replace')
    except Exception:
        return ''
    if len(text) <= limit:
        return text
    return text[:limit] + '\n...[truncated]'


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n', encoding='utf-8')


def scalar(value: Any, fallback: str = 'unknown') -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value.strip() or fallback
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        items = [scalar(item, '') for item in value[:3]]
        items = [item for item in items if item]
        return '; '.join(items) if items else fallback
    return fallback


def latest_goal(goals_dir: Path) -> dict[str, Any]:
    goals: list[dict[str, Any]] = []
    for path in sorted(goals_dir.glob('*.json')):
        data = load_json(path)
        if data:
            data['_path'] = str(path)
            goals.append(data)
    if not goals:
        return {}
    return sorted(goals, key=lambda item: item.get('updated_at') or item.get('created_at') or '', reverse=True)[0]


def latest_run_id(runs_dir: Path) -> str:
    runs = [path for path in runs_dir.glob('*') if path.is_dir()]
    if not runs:
        return ''
    return sorted(runs, key=lambda path: path.stat().st_mtime, reverse=True)[0].name


def resolve_run_and_goal(repo_root: Path, run_id: str, goal_id: str) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    current_run = load_json(repo_root / '.zoo-agent' / 'current-run.json')
    resolved_run = run_id or scalar(current_run.get('run_id'), '')
    if not resolved_run:
        resolved_run = latest_run_id(repo_root / '.zoo-agent' / 'runs')
    run_dir = repo_root / '.zoo-agent' / 'runs' / resolved_run if resolved_run else repo_root / '.zoo-agent' / 'runs' / 'unknown'
    run_ledger = load_json(run_dir / 'run-ledger.json')

    resolved_goal = goal_id or scalar(current_run.get('goal_id') or current_run.get('active_goal_id'), '')
    if not resolved_goal:
        resolved_goal = scalar(run_ledger.get('goal_id') or run_ledger.get('active_goal_id'), '')
    goal = {}
    if resolved_goal:
        goal = load_json(repo_root / '.zoo-agent' / 'goals' / f'{resolved_goal}.json')
        if goal:
            goal['_path'] = str(repo_root / '.zoo-agent' / 'goals' / f'{resolved_goal}.json')
    if not goal:
        goal = latest_goal(repo_root / '.zoo-agent' / 'goals')
        resolved_goal = scalar(goal.get('goal_id'), resolved_goal or 'unknown')
    return resolved_run or 'unknown', resolved_goal or 'unknown', current_run, goal


def checkbox_status(mark: str) -> str:
    mark = mark.strip().lower()
    if mark == 'x':
        return 'done'
    if mark == '!':
        return 'blocked'
    if mark == '-':
        return 'paused'
    if mark == '~':
        return 'redo_needed'
    if mark == '?':
        return 'needs_user_decision'
    return 'active'


def parse_checkbox_board(path: Path) -> list[dict[str, Any]]:
    rows = []
    text = read_text(path)
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = CHECKBOX_RE.match(line)
        if not match:
            continue
        status = checkbox_status(match.group(1))
        title = match.group(2).strip()
        rows.append(
            {
                'id': f'{path.name}:{line_no}',
                'title': title[:240],
                'status': status,
                'source': str(path),
                'line': line_no,
            }
        )
    return rows


def extract_structured_rows(payload: Any, source: str, rows: list[dict[str, Any]], seen: set[str], depth: int = 0) -> None:
    if depth > 7:
        return
    if isinstance(payload, dict):
        status = payload.get('status') or payload.get('state') or payload.get('current_state')
        item_id = payload.get('task_id') or payload.get('branch_id') or payload.get('id') or payload.get('name')
        title = payload.get('objective') or payload.get('title') or payload.get('summary') or payload.get('description')
        if item_id or (status and title):
            row_id = scalar(item_id, f'{source}:{len(rows) + 1}')
            key = f'{source}:{row_id}:{status}:{title}'
            if key not in seen:
                seen.add(key)
                rows.append(
                    {
                        'id': row_id,
                        'title': scalar(title, ''),
                        'status': scalar(status, 'unknown'),
                        'source': source,
                    }
                )
        for value in payload.values():
            if isinstance(value, (dict, list)):
                extract_structured_rows(value, source, rows, seen, depth + 1)
    elif isinstance(payload, list):
        for item in payload:
            extract_structured_rows(item, source, rows, seen, depth + 1)


def collect_task_rows(repo_root: Path, run_id: str) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    run_dir = repo_root / '.zoo-agent' / 'runs' / run_id
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    sources: list[str] = []
    for path in [
        repo_root / '.zoo-agent' / 'TASKS.md',
        repo_root / '.zoo-agent' / 'task-board.md',
        run_dir / 'TASKS.md',
        run_dir / 'task-board.md',
    ]:
        if path.exists():
            sources.append(str(path))
            rows.extend(parse_checkbox_board(path))
    for path in [
        run_dir / 'task-board.json',
        run_dir / 'branch-state.json',
        run_dir / 'run-ledger.json',
        run_dir / 'merge-queue.json',
    ]:
        if path.exists():
            sources.append(str(path))
            extract_structured_rows(load_json(path), path.name, rows, seen)
    counts = collections.Counter(row.get('status') or 'unknown' for row in rows)
    return rows, dict(sorted(counts.items())), sources


def collect_execution_counts(run_dir: Path) -> dict[str, int]:
    return {
        'dispatcher_runs': len(list((run_dir / 'dispatcher-runs').glob('*.json'))),
        'optimistic_runs': len(list((run_dir / 'optimistic-runs').glob('*.json'))),
        'fractal_workstreams': len(list((run_dir / 'fractal-workstreams').glob('*.json'))),
        'codex_results': len(list((run_dir / 'codex-results').glob('*/result.json'))),
        'codex_task_packs': len([path for path in (run_dir / 'codex-tasks').glob('*') if path.is_dir()]),
    }


def open_risks(risk_register: dict[str, Any]) -> list[dict[str, Any]]:
    risks = risk_register.get('risks') if isinstance(risk_register.get('risks'), list) else []
    rows = []
    for risk in risks:
        if not isinstance(risk, dict):
            continue
        status = scalar(risk.get('status'), '')
        if 'closed' in status.lower():
            continue
        rows.append(
            {
                'risk_id': risk.get('risk_id') or risk.get('id') or '',
                'title': risk.get('title') or risk.get('message') or '',
                'severity': risk.get('severity') or '',
                'status': status,
            }
        )
    return rows


def collect_gates(repo_root: Path, run_id: str) -> dict[str, Any]:
    run_dir = repo_root / '.zoo-agent' / 'runs' / run_id
    readiness = load_json(repo_root / '.zoo-agent' / 'project-readiness.json')
    consistency = load_json(run_dir / 'task-board-consistency.json')
    risk_register = load_json(run_dir / 'risk-register.json')
    quality_gate = load_json(run_dir / 'quality-gate.json')
    merge_queue = load_json(run_dir / 'merge-queue.json')
    merge_processing = load_json(run_dir / 'merge-queue-processing.json')
    resource_locks = load_json(repo_root / '.zoo-agent' / 'locks' / 'resource-locks.json')
    architecture = load_json(repo_root / '.zoo-agent' / 'architecture-compatibility-report.json')
    risks = open_risks(risk_register)
    locks = resource_locks.get('locks') if isinstance(resource_locks.get('locks'), list) else []
    readiness_flags = merge_queue.get('readiness_flags') if isinstance(merge_queue.get('readiness_flags'), dict) else {}
    return {
        'project_readiness': {
            'codex_cli_ready': readiness.get('codex_cli_ready', 'unknown'),
            'safe_for_level_0_1_trial': readiness.get('safe_for_level_0_1_trial', 'unknown'),
            'blocking_issue_count': len(readiness.get('blocking_issues') or []) if isinstance(readiness.get('blocking_issues'), list) else 0,
        },
        'architecture_compatibility': {
            'status': architecture.get('status', 'missing'),
            'issue_count': len(architecture.get('issues') or []) if isinstance(architecture.get('issues'), list) else architecture.get('issue_count', 0),
        },
        'task_board_consistency': {
            'status': consistency.get('status', 'missing'),
            'warning_count': len(consistency.get('warnings') or []) if isinstance(consistency.get('warnings'), list) else 0,
        },
        'risk_register': {
            'open_risk_count': len(risks),
            'open_risks': risks[:10],
        },
        'quality_gate': {
            'gate_status': quality_gate.get('gate_status') or quality_gate.get('status') or 'missing',
            'blocker_count': len(quality_gate.get('blockers') or []) if isinstance(quality_gate.get('blockers'), list) else 0,
        },
        'merge_queue': {
            'queue_status': merge_queue.get('queue_status') or merge_queue.get('gate_status') or merge_queue.get('status') or 'missing',
            'approved_for_merge': bool(readiness_flags.get('approved_for_merge')),
            'merge_queue_processing_authorized': bool(readiness_flags.get('merge_queue_processing_authorized')),
        },
        'merge_queue_processing': {
            'status': merge_processing.get('status', 'missing'),
            'processed_count': len(merge_processing.get('processed') or []) if isinstance(merge_processing.get('processed'), list) else 0,
        },
        'resource_locks': {
            'active_lock_count': len(locks),
        },
    }


def next_actions(payload: dict[str, Any]) -> list[str]:
    actions = []
    if not payload['charter'].get('path_exists'):
        actions.append('Create or bind `.zoo-agent/project-charter.json` before non-trivial coding.')
    if not payload['goal'].get('path_exists'):
        actions.append('Create or bind `.zoo-agent/goals/<goal-id>.json` for the active objective.')
    gates = payload.get('gates') or {}
    if gates.get('task_board_consistency', {}).get('status') in {'missing', 'warnings'}:
        actions.append('Refresh/apply the task board before continuing or claiming completion.')
    if gates.get('risk_register', {}).get('open_risk_count', 0):
        actions.append('Close or explicitly carry open risks before integration.')
    if gates.get('quality_gate', {}).get('gate_status') in {'missing', 'fail', 'blocked'}:
        actions.append('Run or re-run the quality gate for the active run.')
    if gates.get('resource_locks', {}).get('active_lock_count', 0):
        actions.append('Review active resource locks before starting parallel workers.')
    if not actions:
        actions.append('Continue the active run or review merge readiness from this board.')
    return actions


def build_board(repo_root: Path, run_id: str, goal_id: str) -> dict[str, Any]:
    run_id, goal_id, current_run, goal = resolve_run_and_goal(repo_root, run_id, goal_id)
    run_dir = repo_root / '.zoo-agent' / 'runs' / run_id
    charter_path = repo_root / '.zoo-agent' / 'project-charter.json'
    charter = load_json(charter_path)
    task_rows, task_status_counts, task_sources = collect_task_rows(repo_root, run_id)
    gates = collect_gates(repo_root, run_id)
    payload = {
        'schema_version': '1.0',
        'generated_by': 'render_governance_board.py',
        'generated_at': utc_now(),
        'workspace': str(repo_root),
        'run_id': run_id,
        'goal_id': goal_id,
        'current_run': current_run,
        'charter': {
            'path': str(charter_path),
            'path_exists': charter_path.exists(),
            'mission': scalar(charter.get('mission') or charter.get('project_mission') or charter.get('summary')),
            'product_goals': charter.get('product_goals') or [],
            'technical_goals': charter.get('technical_goals') or [],
            'non_goals': charter.get('non_goals') or [],
            'quality_bar': scalar(charter.get('quality_bar')),
        },
        'goal': {
            'goal_id': goal_id,
            'path': goal.get('_path') or str(repo_root / '.zoo-agent' / 'goals' / f'{goal_id}.json'),
            'path_exists': bool(goal),
            'root_goal': scalar(goal.get('root_goal')),
            'success_criteria': goal.get('success_criteria') or [],
            'failure_criteria': goal.get('failure_criteria') or [],
            'non_goals': goal.get('non_goals') or [],
            'updated_at': goal.get('updated_at', ''),
        },
        'run': {
            'run_dir': str(run_dir),
            'exists': run_dir.exists(),
            'current_state': scalar(current_run.get('current_state') or load_json(run_dir / 'status.json').get('current_state')),
            'active_branch': scalar(current_run.get('active_branch') or load_json(run_dir / 'status.json').get('active_branch')),
        },
        'tasks': {
            'source_files': task_sources,
            'total_count': len(task_rows),
            'status_counts': task_status_counts,
            'active_or_blocked': [
                row for row in task_rows if row.get('status') in {'active', 'blocked', 'redo_needed', 'paused', 'needs_user_decision'}
            ][:20],
        },
        'execution': collect_execution_counts(run_dir),
        'gates': gates,
        'source_of_truth': {
            'durable_project': ['.zoo-agent/project-charter.json', '.zoo-agent/project-profile.json', '.zoo-agent/project-map.json'],
            'durable_goals': ['.zoo-agent/goals/<goal-id>.json'],
            'active_run': ['.zoo-agent/current-run.json', '.zoo-agent/runs/<run-id>/'],
            'human_task_board': ['.zoo-agent/TASKS.md', '.zoo-agent/runs/<run-id>/TASKS.md'],
            'machine_task_state': ['.zoo-agent/runs/<run-id>/task-board.json', '.zoo-agent/runs/<run-id>/branch-state.json'],
            'worker_task_packs': ['.zoo-agent/runs/<run-id>/codex-tasks/<task-id>/TASKS.yaml'],
        },
    }
    payload['next_actions'] = next_actions(payload)
    return payload


def md_list(items: Any, empty: str = 'unknown', limit: int = 6) -> list[str]:
    if not isinstance(items, list) or not items:
        return [f'- {empty}']
    return [f'- {scalar(item)}' for item in items[:limit]]


def render_markdown(payload: dict[str, Any]) -> str:
    charter = payload['charter']
    goal = payload['goal']
    run = payload['run']
    tasks = payload['tasks']
    execution = payload['execution']
    gates = payload['gates']
    lines = [
        '# Zoo Governance Board',
        '',
        f"- generated_at: `{payload['generated_at']}`",
        f"- workspace: `{payload['workspace']}`",
        f"- run_id: `{payload['run_id']}`",
        f"- goal_id: `{payload['goal_id']}`",
        f"- current_state: `{run.get('current_state', 'unknown')}`",
        f"- active_branch: `{run.get('active_branch', 'unknown')}`",
        '',
        '## Durable Aim',
        '',
        f"- charter: `{'present' if charter.get('path_exists') else 'missing'}`",
        f"- mission: {charter.get('mission', 'unknown')}",
        f"- goal: `{'present' if goal.get('path_exists') else 'missing'}`",
        f"- root_goal: {goal.get('root_goal', 'unknown')}",
        '',
        '### Success Criteria',
        '',
    ]
    lines.extend(md_list(goal.get('success_criteria'), 'unknown'))
    lines += ['', '### Non-Goals', '']
    non_goals = goal.get('non_goals') or charter.get('non_goals') or []
    lines.extend(md_list(non_goals, 'unknown'))
    lines += [
        '',
        '## Task Progress',
        '',
        f"- total_tasks_seen: `{tasks.get('total_count', 0)}`",
    ]
    counts = tasks.get('status_counts') or {}
    if counts:
        for status, count in sorted(counts.items()):
            lines.append(f"- {status}: `{count}`")
    else:
        lines.append('- status_counts: `none`')
    lines += ['', '### Active / Blocked / Needs Decision', '']
    active = tasks.get('active_or_blocked') or []
    if not active:
        lines.append('- none')
    else:
        for row in active[:12]:
            label = row.get('title') or row.get('id') or 'untitled'
            lines.append(f"- `{row.get('status', 'unknown')}` {row.get('id', '')}: {label}")
    lines += [
        '',
        '## Execution Evidence',
        '',
    ]
    for key, value in execution.items():
        lines.append(f"- {key}: `{value}`")
    lines += ['', '## Governance Gates', '']
    gate_rows = [
        ('project_readiness.codex_cli_ready', gates.get('project_readiness', {}).get('codex_cli_ready')),
        ('project_readiness.safe_for_level_0_1_trial', gates.get('project_readiness', {}).get('safe_for_level_0_1_trial')),
        ('architecture_compatibility.status', gates.get('architecture_compatibility', {}).get('status')),
        ('task_board_consistency.status', gates.get('task_board_consistency', {}).get('status')),
        ('task_board_consistency.warning_count', gates.get('task_board_consistency', {}).get('warning_count')),
        ('risk_register.open_risk_count', gates.get('risk_register', {}).get('open_risk_count')),
        ('quality_gate.gate_status', gates.get('quality_gate', {}).get('gate_status')),
        ('quality_gate.blocker_count', gates.get('quality_gate', {}).get('blocker_count')),
        ('merge_queue.queue_status', gates.get('merge_queue', {}).get('queue_status')),
        ('merge_queue.approved_for_merge', gates.get('merge_queue', {}).get('approved_for_merge')),
        ('resource_locks.active_lock_count', gates.get('resource_locks', {}).get('active_lock_count')),
    ]
    for name, value in gate_rows:
        lines.append(f"- {name}: `{scalar(value)}`")
    lines += ['', '## Next Actions', '']
    for action in payload.get('next_actions') or []:
        lines.append(f"- {action}")
    lines += ['', '## Source Files', '']
    for group, paths in (payload.get('source_of_truth') or {}).items():
        lines.append(f"- {group}: {', '.join(f'`{path}`' for path in paths)}")
    lines += ['', '## Task Board Sources', '']
    if tasks.get('source_files'):
        for path in tasks['source_files']:
            lines.append(f"- `{path}`")
    else:
        lines.append('- none')
    return '\n'.join(lines) + '\n'


def main() -> int:
    ap = argparse.ArgumentParser(description='Render a single read-only Zoo governance board from durable and run artifacts.')
    ap.add_argument('--workspace', default='.', help='Project workspace. Defaults to current directory.')
    ap.add_argument('--run-id', default='', help='Run id. Defaults to .zoo-agent/current-run.json or latest run directory.')
    ap.add_argument('--goal-id', default='', help='Goal id. Defaults to current run goal or latest goal.')
    ap.add_argument('--output', default='', help='Markdown output. Defaults to .zoo-agent/BOARD.md.')
    ap.add_argument('--json-output', default='', help='JSON output. Defaults to .zoo-agent/status-board.json.')
    ap.add_argument('--no-run-archive', action='store_true', help='Do not mirror BOARD.md/status-board.json into the run directory.')
    args = ap.parse_args()

    repo_root = git_root(Path(args.workspace).resolve())
    payload = build_board(repo_root, args.run_id, args.goal_id)
    board_md = Path(args.output).resolve() if args.output else repo_root / '.zoo-agent' / 'BOARD.md'
    board_json = Path(args.json_output).resolve() if args.json_output else repo_root / '.zoo-agent' / 'status-board.json'
    write_text(board_md, render_markdown(payload))
    write_json(board_json, payload)
    if not args.no_run_archive and payload['run_id'] != 'unknown':
        run_dir = repo_root / '.zoo-agent' / 'runs' / payload['run_id']
        write_text(run_dir / 'BOARD.md', render_markdown(payload))
        write_json(run_dir / 'status-board.json', payload)
    print(json.dumps({'status': 'ok', 'board': str(board_md), 'json': str(board_json), 'run_id': payload['run_id'], 'goal_id': payload['goal_id']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
