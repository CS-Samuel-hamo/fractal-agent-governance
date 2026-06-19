from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def safe_name(value: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in '._-' else '-' for ch in str(value)).strip('-') or 'item'


def project_root(workspace: str | Path) -> Path:
    root = Path(workspace).resolve()
    if not root.exists():
        raise SystemExit(f'Missing workspace: {root}')
    proc = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        cwd=root,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return Path(proc.stdout.strip()).resolve()
    return root


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def latest_goal(project: Path) -> dict[str, Any]:
    goals_dir = project / '.zoo-agent' / 'goals'
    goals: list[dict[str, Any]] = []
    for path in sorted(goals_dir.glob('*.json')):
        payload = load_json(path)
        if payload:
            payload['_path'] = str(path)
            goals.append(payload)
    if not goals:
        return {}
    return sorted(goals, key=lambda item: item.get('updated_at') or item.get('created_at') or '', reverse=True)[0]


def resolve_goal(project: Path, goal_id: str = '', run_id: str = '') -> dict[str, Any]:
    if goal_id:
        path = project / '.zoo-agent' / 'goals' / f'{safe_name(goal_id)}.json'
        payload = load_json(path)
        if payload:
            payload['_path'] = str(path)
        return payload

    current_run = load_json(project / '.zoo-agent' / 'current-run.json')
    active_goal_id = current_run.get('goal_id') or current_run.get('active_goal_id')
    if active_goal_id:
        goal = resolve_goal(project, str(active_goal_id))
        if goal:
            return goal

    if run_id:
        run_ledger = load_json(project / '.zoo-agent' / 'runs' / run_id / 'run-ledger.json')
        active_goal_id = run_ledger.get('goal_id') or run_ledger.get('active_goal_id')
        if active_goal_id:
            goal = resolve_goal(project, str(active_goal_id))
            if goal:
                return goal

    return latest_goal(project)


def default_goal_id(goal_text: str) -> str:
    stamp = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    label = safe_name(goal_text[:48]).lower() or 'goal'
    return f'goal-{stamp}-{label}'


def set_active_goal(
    project: Path,
    goal_text: str,
    *,
    goal_id: str = '',
    run_id: str = '',
    success_criteria: list[str] | None = None,
    constraints: list[str] | None = None,
    activate: bool = True,
    source: str = 'set_goal.py',
) -> dict[str, Any]:
    now = utc_now()
    goal_id = safe_name(goal_id or default_goal_id(goal_text))
    path = project / '.zoo-agent' / 'goals' / f'{goal_id}.json'
    existing = load_json(path)
    payload = {
        **existing,
        'schema_version': '1.0',
        'goal_id': goal_id,
        'root_goal': goal_text,
        'success_criteria': success_criteria or existing.get('success_criteria') or [],
        'constraints': constraints or existing.get('constraints') or [],
        'status': 'active' if activate else existing.get('status', 'draft'),
        'source_of_truth': True,
        'created_at': existing.get('created_at') or now,
        'updated_at': now,
        'generated_by': source,
    }
    write_json(path, payload)

    if activate:
        current_path = project / '.zoo-agent' / 'current-run.json'
        current = load_json(current_path)
        current.update(
            {
                'goal_id': goal_id,
                'active_goal_id': goal_id,
                'updated_at': now,
            }
        )
        if run_id:
            current['run_id'] = run_id
        write_json(current_path, current)

        goal_state = {
            'schema_version': '1.0',
            'generated_by': source,
            'updated_at': now,
            'active_goal_id': goal_id,
            'source_of_truth': str(path),
            'rule': 'goal_is_the_runtime_source_of_truth',
        }
        write_json(project / '.zoo-agent' / 'goal_state.json', goal_state)

    payload['_path'] = str(path)
    return payload


def ensure_goal(project: Path, *, goal_id: str = '', run_id: str = '', fallback_goal: str = '') -> dict[str, Any]:
    goal = resolve_goal(project, goal_id, run_id)
    if goal:
        return goal
    text = fallback_goal or 'Operate this project through the CLI-first AI Agent Runtime with bounded Codex execution.'
    return set_active_goal(project, text, goal_id=goal_id, run_id=run_id, source='agent_runtime_v4')


def tokenize(text: str) -> set[str]:
    normalized = ''.join(ch.lower() if ch.isalnum() else ' ' for ch in text)
    stop = {
        'the', 'and', 'for', 'with', 'from', 'this', 'that', 'into', 'task', 'goal',
        'project', 'system', 'runtime', 'agent', 'code', 'make', 'update', 'fix',
        'implement', 'add', 'use', 'to', 'of', 'in', 'on', 'a', 'an',
    }
    return {part for part in normalized.split() if len(part) > 2 and part not in stop}


def alignment_report(
    project: Path,
    *,
    objective: str,
    task_id: str,
    run_id: str,
    goal_id: str = '',
    source: str = 'check_goal_alignment.py',
) -> dict[str, Any]:
    goal = resolve_goal(project, goal_id, run_id)
    if not goal:
        return {
            'schema_version': '1.0',
            'generated_by': source,
            'generated_at': utc_now(),
            'run_id': run_id,
            'task_id': task_id,
            'goal_id': goal_id or '',
            'status': 'blocked',
            'alignment_score': 0.0,
            'basis': ['No active goal was found.'],
            'blockers': ['missing_goal'],
        }

    goal_text = ' '.join(
        [
            str(goal.get('root_goal') or ''),
            ' '.join(str(item) for item in goal.get('success_criteria') or []),
            ' '.join(str(item) for item in goal.get('constraints') or []),
        ]
    )
    objective_tokens = tokenize(objective)
    goal_tokens = tokenize(goal_text)
    matched = sorted(objective_tokens & goal_tokens)
    score = round(len(matched) / max(len(objective_tokens), 1), 3)
    constraint_hits = []
    objective_lower = objective.lower()
    for item in goal.get('constraints') or []:
        text = str(item).lower()
        if text and text in objective_lower:
            constraint_hits.append(str(item))

    status = 'pass'
    blockers: list[str] = []
    warnings: list[str] = []
    if score < 0.08 and not matched:
        status = 'needs_review'
        warnings.append('low_goal_term_overlap')
    if constraint_hits:
        status = 'blocked'
        blockers.append('objective_mentions_goal_constraint')

    return {
        'schema_version': '1.0',
        'generated_by': source,
        'generated_at': utc_now(),
        'run_id': run_id,
        'task_id': task_id,
        'goal_id': goal.get('goal_id') or goal_id,
        'goal_path': goal.get('_path', ''),
        'status': status,
        'alignment_score': score,
        'matched_terms': matched[:40],
        'basis': [
            'Compared current task objective tokens with active goal, success criteria, and constraints.',
            'Low overlap is review evidence, not an automatic semantic contradiction.',
        ],
        'warnings': warnings,
        'blockers': blockers,
        'constraint_hits': constraint_hits,
    }


def initialize_loop(project: Path, *, max_iteration: int = 10, source: str = 'agent_runtime_v4') -> dict[str, Any]:
    path = project / '.zoo-agent' / 'loop_state.json'
    state = load_json(path)
    if not state:
        state = {
            'iteration': 0,
            'max_iteration': max_iteration,
            'status': 'active',
            'drift_detected': False,
        }
    state.update({'updated_at': utc_now(), 'generated_by': source})
    state['max_iteration'] = int(state.get('max_iteration') or max_iteration)
    write_json(path, state)
    return state


def advance_loop(project: Path, *, run_id: str, task_id: str, max_iteration: int = 10) -> dict[str, Any]:
    state = initialize_loop(project, max_iteration=max_iteration)
    state['iteration'] = int(state.get('iteration') or 0) + 1
    state['max_iteration'] = int(state.get('max_iteration') or max_iteration)
    if state['iteration'] > state['max_iteration']:
        state['status'] = 'diverging'
        state['drift_detected'] = True
        state['recommended_escalation'] = 'gpt_decision_layer'
    elif state.get('status') not in {'converged', 'diverging'}:
        state['status'] = 'active'
        state['drift_detected'] = bool(state.get('drift_detected', False))
    state.update({'updated_at': utc_now(), 'run_id': run_id, 'task_id': task_id})
    write_json(project / '.zoo-agent' / 'loop_state.json', state)
    write_json(project / '.zoo-agent' / 'runs' / run_id / 'loop_state.json', state)
    return state
