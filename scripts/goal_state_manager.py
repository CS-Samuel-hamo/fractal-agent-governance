#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from classify_goal_domain import classify_goal
from runtime_common import load_json, project_root, resolve_goal, safe_name, utc_now, write_json

GOAL_STATUSES = {'active', 'paused', 'completed', 'blocked', 'backlog'}
STICKY_FIELDS = {
    'priority',
    'status',
    'resource_usage',
    'depends_on',
    'blocks',
    'created_at',
    'manual_priority',
    'blocking_reason',
    'backlog_reason',
    'human_decision_required',
    'risk_level',
}
LEGAL_STATUS_TRANSITIONS = {
    'active': {'completed', 'blocked', 'paused'},
    'paused': {'active', 'backlog', 'blocked', 'completed'},
    'backlog': {'active', 'blocked'},
    'blocked': {'paused', 'backlog'},
    'completed': set(),
}
REASON_REQUIRED_TRANSITIONS = {
    ('blocked', 'paused'),
    ('blocked', 'backlog'),
    ('backlog', 'active'),
}


def state_paths(project: Path) -> tuple[Path, Path]:
    return project / '.zoo-agent' / 'goal' / 'goal_state.json', project / '.zoo-agent' / 'goal_state.json'


def infer_resource_usage(goal: dict[str, Any], explicit: list[str] | None = None) -> list[str]:
    resources = [str(item).strip() for item in explicit or [] if str(item).strip()]
    if resources:
        return sorted(set(resources))
    text = ' '.join(
        [
            str(goal.get('goal') or ''),
            str(goal.get('root_goal') or ''),
            ' '.join(str(item) for item in goal.get('success_criteria') or []),
        ]
    )
    lowered = text.lower()
    inferred: set[str] = set()
    try:
        from big_task_common import infer_paths

        inferred.update(infer_paths(text))
    except Exception:
        pass
    if any(term in lowered for term in ['api', 'endpoint', 'route', 'contract', 'public api']):
        inferred.add('api_contract:*')
    if any(term in lowered for term in ['schema', 'dto', 'model']):
        inferred.add('schema:*')
    if any(term in lowered for term in ['database', 'db', 'migration', 'table']):
        inferred.add('database:*')
    if any(term in lowered for term in ['auth', 'security', 'permission']):
        inferred.add('auth_security:*')
    if any(term in lowered for term in ['readme', 'docs', 'documentation']):
        inferred.add('documentation_surface:*')
    return sorted(inferred)


def normalize_progress(value: Any) -> int:
    try:
        numeric = float(value or 0.0)
    except Exception:
        return 0
    if numeric <= 1.0:
        numeric *= 100
    return max(0, min(100, int(numeric)))


def goal_record_from_payload(
    goal: dict[str, Any],
    *,
    status: str = '',
    priority: int | None = None,
    resources: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    goal_id = str(goal.get('goal_id') or '').strip()
    raw_priority = priority if priority is not None else goal.get('priority', 50)
    try:
        normalized_priority = max(0, min(100, int(raw_priority)))
    except Exception:
        normalized_priority = 50
    goal_status = status or str(goal.get('scheduler_status') or goal.get('status') or 'paused')
    if goal_status not in GOAL_STATUSES:
        goal_status = 'paused'
    classified = classify_goal({**goal, 'goal_id': goal_id})
    return {
        'goal_id': goal_id,
        'goal': str(goal.get('goal') or goal.get('root_goal') or ''),
        'goal_type': classified['goal_type'],
        'execution_mode': classified['execution_mode'],
        'status': goal_status,
        'priority': normalized_priority,
        'progress': normalize_progress(
            goal.get('progress') if goal.get('progress') is not None else goal.get('progress_score')
        ),
        'resource_usage': infer_resource_usage(goal, resources),
        'depends_on': [str(item) for item in depends_on if str(item).strip()]
        if depends_on is not None
        else [str(item) for item in goal.get('depends_on') or []],
        'blocks': [str(item) for item in goal.get('blocks') or []],
        'last_active': str(goal.get('last_active') or ''),
        'continuous_iterations': int(goal.get('continuous_iterations') or 0),
        'starvation_count': int(goal.get('starvation_count') or 0),
        'created_at': str(goal.get('created_at') or utc_now()),
        'updated_at': utc_now(),
    }


def _legacy_active_goal_id(project: Path, state: dict[str, Any]) -> str:
    return str(
        state.get('active_goal_id')
        or (state.get('global_loop_state') or {}).get('active_goal_id')
        or (load_json(project / '.zoo-agent' / 'current-run.json').get('active_goal_id'))
        or ''
    )


def is_goal_record_payload(payload: dict[str, Any]) -> bool:
    return bool(payload.get('goal_id') and (payload.get('goal') or payload.get('root_goal')))


def load_goal_state(project: Path) -> dict[str, Any]:
    new_path, legacy_path = state_paths(project)
    raw = load_json(new_path) or load_json(legacy_path)
    if isinstance(raw.get('goals'), list) and isinstance(raw.get('global_loop_state'), dict):
        raw['goals'] = [
            dict(item)
            for item in raw.get('goals') or []
            if isinstance(item, dict) and item.get('goal_id') and (item.get('goal') or item.get('root_goal'))
        ]
        raw.setdefault('revision', 0)
        raw.setdefault('event_log', [])
        return raw
    active_goal_id = _legacy_active_goal_id(project, raw)
    goals: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted((project / '.zoo-agent' / 'goals').glob('*.json')):
        payload = load_json(path)
        if not is_goal_record_payload(payload):
            continue
        goal_id = str(payload.get('goal_id') or path.stem)
        if not goal_id or goal_id in seen:
            continue
        status = 'active' if goal_id == active_goal_id else 'paused'
        goals.append(goal_record_from_payload(payload, status=status))
        seen.add(goal_id)
    current = load_json(project / '.zoo-agent' / 'goal' / 'current-goal.json')
    if current and str(current.get('goal_id') or '') not in seen:
        goals.append(goal_record_from_payload(current, status='active'))
        active_goal_id = str(current.get('goal_id') or active_goal_id)
    if not active_goal_id and goals:
        active_goal_id = str(goals[0].get('goal_id') or '')
    state = {
        'schema_version': '2.0',
        'generated_by': 'goal_state_manager.py',
        'revision': 0,
        'updated_at': utc_now(),
        'goals': goals,
        'global_loop_state': {
            'iteration': 0,
            'max_iterations': 100,
            'system_status': 'active' if goals else 'converged',
            'active_goal_id': active_goal_id,
        },
        'goal_id': active_goal_id,
        'active_goal_id': active_goal_id,
        'status': 'active' if active_goal_id else 'converged',
        'progress_score': 0.0,
        'event_log': [],
    }
    return state


def write_goal_state(project: Path, state: dict[str, Any]) -> dict[str, str]:
    new_path, legacy_path = state_paths(project)
    state['schema_version'] = '2.0'
    state.setdefault('revision', 0)
    state.setdefault('event_log', [])
    state['updated_at'] = utc_now()
    goals = state.get('goals') if isinstance(state.get('goals'), list) else []
    active_goal_id = str(
        (state.get('global_loop_state') or {}).get('active_goal_id') or state.get('active_goal_id') or ''
    )
    active = next((item for item in goals if item.get('goal_id') == active_goal_id), {})
    state['goal_id'] = active_goal_id
    state['active_goal_id'] = active_goal_id
    state['status'] = active.get('status') or state.get('status') or ('active' if active_goal_id else 'converged')
    state['progress_score'] = round(float(active.get('progress') or 0) / 100.0, 3) if active else 0.0
    write_json(new_path, state)
    write_json(legacy_path, state)
    return {'goal_state': str(new_path), 'legacy_goal_state': str(legacy_path)}


def _goal_map(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get('goal_id') or ''): item for item in state.get('goals') or [] if item.get('goal_id')}


def _goal_or_fail(state: dict[str, Any], goal_id: str) -> dict[str, Any]:
    goal = _goal_map(state).get(goal_id)
    if not goal:
        raise ValueError(f'unknown_goal:{goal_id}')
    return goal


def _reason(change: dict[str, Any], patch: dict[str, Any]) -> str:
    return str(change.get('reason') or patch.get('reason') or '').strip()


def _validate_status_transition(old: str, new: str, reason: str) -> None:
    if old == new:
        return
    if old not in GOAL_STATUSES or new not in GOAL_STATUSES:
        raise ValueError(f'illegal_status_value:{old}->{new}')
    if new not in LEGAL_STATUS_TRANSITIONS.get(old, set()):
        raise ValueError(f'illegal_status_transition:{old}->{new}')
    if (old, new) in REASON_REQUIRED_TRANSITIONS and not reason:
        raise ValueError(f'missing_reason_for_status_transition:{old}->{new}')


def _deactivate_other_active_goals(state: dict[str, Any], active_goal_id: str, reason: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for goal in state.get('goals') or []:
        goal_id = str(goal.get('goal_id') or '')
        if goal_id != active_goal_id and goal.get('status') == 'active':
            goal['status'] = 'paused'
            goal['updated_at'] = utc_now()
            events.append(
                {
                    'goal_id': goal_id,
                    'op': 'set_status',
                    'from': 'active',
                    'to': 'paused',
                    'reason': reason or 'single_goal_mode_pause_previous_active',
                }
            )
    return events


def validate_goal_state_invariants(state: dict[str, Any]) -> None:
    blockers: list[str] = []
    seen: set[str] = set()
    active_count = 0
    for goal in state.get('goals') or []:
        goal_id = str(goal.get('goal_id') or '')
        status = str(goal.get('status') or '')
        if not goal_id:
            blockers.append('missing_goal_id')
            continue
        if goal_id in seen:
            blockers.append(f'duplicate_goal_id:{goal_id}')
        seen.add(goal_id)
        if status not in GOAL_STATUSES:
            blockers.append(f'invalid_goal_status:{goal_id}:{status}')
        if status == 'active':
            active_count += 1
        if status == 'completed' and str((state.get('global_loop_state') or {}).get('active_goal_id') or '') == goal_id:
            blockers.append(f'completed_goal_marked_active:{goal_id}')
    if active_count > 1:
        blockers.append(f'multiple_active_goals:{active_count}')
    if blockers:
        raise ValueError('invariant_failed:' + ','.join(blockers))


def build_state_patch(
    project: Path,
    *,
    source: str,
    reason: str,
    changes: list[dict[str, Any]],
    patch_id: str = '',
) -> dict[str, Any]:
    state = load_goal_state(project)
    stamp = utc_now().replace(':', '').replace('-', '')
    return {
        'schema_version': '1.0',
        'patch_id': patch_id or f'patch-{stamp}-{safe_name(source)}',
        'created_at': utc_now(),
        'source': source,
        'reason': reason,
        'base_revision': int(state.get('revision') or 0),
        'changes': changes,
    }


def apply_goal_state_patch_data(
    project: Path,
    patch: dict[str, Any],
    *,
    write_diff: bool = True,
) -> dict[str, Any]:
    state = load_goal_state(project)
    base_revision = patch.get('base_revision')
    current_revision = int(state.get('revision') or 0)
    if base_revision is not None and int(base_revision) != current_revision:
        raise ValueError(f'base_revision_mismatch:{base_revision}!={current_revision}')

    before = json.loads(json.dumps(state, ensure_ascii=False))
    events: list[dict[str, Any]] = []
    loop = state.setdefault('global_loop_state', {})
    for change in patch.get('changes') or []:
        if not isinstance(change, dict):
            raise ValueError('invalid_change')
        op = str(change.get('op') or '')
        goal_id = str(change.get('goal_id') or '')
        reason = _reason(change, patch)
        if op == 'append_event':
            events.append({'goal_id': goal_id, 'op': op, 'reason': reason, 'payload': change.get('payload') or {}})
            continue
        if op == 'set_loop_status':
            loop_key = str(change.get('field') or 'system_status')
            loop[loop_key] = change.get('to')
            events.append({'goal_id': goal_id, 'op': op, 'field': loop_key, 'to': change.get('to'), 'reason': reason})
            continue
        if op == 'freeze_actual_execution':
            loop['actual_execution_frozen'] = True
            loop['system_status'] = 'degraded'
            loop['active_goal_id'] = ''
            loop['active_goal'] = ''
            for goal in state.get('goals') or []:
                if goal.get('status') == 'active':
                    _validate_status_transition('active', 'paused', reason or 'backend_unhealthy_freeze')
                    goal['status'] = 'paused'
                    goal['freeze_reason'] = reason or 'backend_unhealthy_freeze'
                    goal['updated_at'] = utc_now()
                    events.append(
                        {
                            'goal_id': goal.get('goal_id'),
                            'op': 'set_status',
                            'from': 'active',
                            'to': 'paused',
                            'reason': reason or 'backend_unhealthy_freeze',
                        }
                    )
            continue

        goal = _goal_or_fail(state, goal_id)
        old_status = str(goal.get('status') or 'paused')
        if op == 'set_status':
            new_status = str(change.get('to') or '')
            _validate_status_transition(old_status, new_status, reason)
            goal['status'] = new_status
            goal['updated_at'] = utc_now()
            if new_status == 'active':
                goal['last_active'] = utc_now()
                loop['active_goal_id'] = goal_id
                loop['active_goal'] = goal_id
                events.extend(_deactivate_other_active_goals(state, goal_id, reason))
            elif loop.get('active_goal_id') == goal_id:
                loop['active_goal_id'] = ''
                loop['active_goal'] = ''
            events.append({'goal_id': goal_id, 'op': op, 'from': old_status, 'to': new_status, 'reason': reason})
        elif op == 'set_active':
            new_status = 'active' if bool(change.get('to', True)) else 'paused'
            _validate_status_transition(old_status, new_status, reason or 'scheduler_active_switch')
            goal['status'] = new_status
            goal['updated_at'] = utc_now()
            if new_status == 'active':
                goal['last_active'] = utc_now()
                loop['active_goal_id'] = goal_id
                loop['active_goal'] = goal_id
                events.extend(_deactivate_other_active_goals(state, goal_id, reason))
            events.append({'goal_id': goal_id, 'op': op, 'from': old_status, 'to': new_status, 'reason': reason})
        elif op == 'set_progress':
            old = goal.get('progress')
            goal['progress'] = normalize_progress(change.get('to'))
            goal['updated_at'] = utc_now()
            events.append({'goal_id': goal_id, 'op': op, 'from': old, 'to': goal['progress'], 'reason': reason})
        elif op == 'set_priority':
            if not reason:
                raise ValueError('missing_reason_for_set_priority')
            old = goal.get('priority')
            goal['priority'] = max(0, min(100, int(change.get('to'))))
            goal['manual_priority'] = True
            goal['updated_at'] = utc_now()
            events.append({'goal_id': goal_id, 'op': op, 'from': old, 'to': goal['priority'], 'reason': reason})
        elif op == 'set_resource_usage':
            if not reason:
                raise ValueError('missing_reason_for_set_resource_usage')
            old = goal.get('resource_usage') or []
            goal['resource_usage'] = sorted(set(str(item) for item in change.get('to') or [] if str(item).strip()))
            goal['updated_at'] = utc_now()
            events.append({'goal_id': goal_id, 'op': op, 'from': old, 'to': goal['resource_usage'], 'reason': reason})
        elif op == 'set_blocker':
            _validate_status_transition(old_status, 'blocked', reason or 'blocker_set')
            goal['status'] = 'blocked'
            goal['blocking_reason'] = reason or str(change.get('to') or 'blocked')
            goal['updated_at'] = utc_now()
            if loop.get('active_goal_id') == goal_id:
                loop['active_goal_id'] = ''
                loop['active_goal'] = ''
            events.append(
                {'goal_id': goal_id, 'op': op, 'from': old_status, 'to': 'blocked', 'reason': goal['blocking_reason']}
            )
        elif op == 'set_backlog':
            _validate_status_transition(old_status, 'backlog', reason or 'backlog_set')
            goal['status'] = 'backlog'
            goal['backlog_reason'] = reason or str(change.get('to') or 'deferred')
            goal['updated_at'] = utc_now()
            if loop.get('active_goal_id') == goal_id:
                loop['active_goal_id'] = ''
                loop['active_goal'] = ''
            events.append(
                {'goal_id': goal_id, 'op': op, 'from': old_status, 'to': 'backlog', 'reason': goal['backlog_reason']}
            )
        elif op == 'set_completion':
            _validate_status_transition(old_status, 'completed', reason or 'goal_completed')
            goal['status'] = 'completed'
            goal['progress'] = 100
            goal['updated_at'] = utc_now()
            if loop.get('active_goal_id') == goal_id:
                loop['active_goal_id'] = ''
                loop['active_goal'] = ''
            events.append(
                {
                    'goal_id': goal_id,
                    'op': op,
                    'from': old_status,
                    'to': 'completed',
                    'reason': reason or 'goal_completed',
                }
            )
        else:
            raise ValueError(f'unsupported_patch_op:{op}')

    validate_goal_state_invariants(state)
    state['revision'] = current_revision + 1
    state.setdefault('event_log', [])
    state['event_log'].extend(
        {
            'patch_id': patch.get('patch_id') or '',
            'source': patch.get('source') or '',
            'created_at': utc_now(),
            **event,
        }
        for event in events
    )
    paths = write_goal_state(project, state)
    diff = render_state_diff(before, state, patch)
    diff_path = project / '.zoo-agent' / 'goal' / 'goal-state-diff.md'
    if write_diff:
        write_json(project / '.zoo-agent' / 'goal' / 'last-applied-state-patch.json', patch)
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text(diff, encoding='utf-8')
    return {'state': state, 'paths': {**paths, 'goal_state_diff': str(diff_path)}, 'events': events}


def render_state_diff(before: dict[str, Any], after: dict[str, Any], patch: dict[str, Any]) -> str:
    before_goals = _goal_map(before)
    after_goals = _goal_map(after)
    lines = [
        '# Goal State Diff',
        '',
        f'- patch_id: `{patch.get("patch_id") or ""}`',
        f'- source: `{patch.get("source") or ""}`',
        f'- reason: `{patch.get("reason") or ""}`',
        f'- revision: `{before.get("revision", 0)}` -> `{after.get("revision", 0)}`',
        '',
        '## Changes',
    ]
    for goal_id, after_goal in after_goals.items():
        before_goal = before_goals.get(goal_id, {})
        changed: list[str] = []
        for field in ['status', 'priority', 'progress', 'resource_usage', 'depends_on', 'blocks']:
            if before_goal.get(field) != after_goal.get(field):
                changed.append(f'- `{goal_id}.{field}`: `{before_goal.get(field)}` -> `{after_goal.get(field)}`')
        lines.extend(changed or [f'- `{goal_id}` unchanged'])
    return '\n'.join(lines) + '\n'


def sync_goals(project: Path) -> dict[str, Any]:
    state = load_goal_state(project)
    existing = {str(item.get('goal_id')): dict(item) for item in state.get('goals') or []}
    for path in sorted((project / '.zoo-agent' / 'goals').glob('*.json')):
        payload = load_json(path)
        if not is_goal_record_payload(payload):
            continue
        goal_id = str(payload.get('goal_id') or path.stem)
        if not goal_id:
            continue
        if goal_id in existing:
            record = existing[goal_id]
            record['goal'] = str(payload.get('goal') or payload.get('root_goal') or record.get('goal') or '')
            classified = classify_goal({**payload, **record})
            record['goal_type'] = classified['goal_type']
            record['execution_mode'] = classified['execution_mode']
            if not record.get('resource_usage'):
                record['resource_usage'] = infer_resource_usage(payload)
            record['updated_at'] = utc_now()
            existing[goal_id] = record
        else:
            existing[goal_id] = goal_record_from_payload(payload, status='paused')
    state['goals'] = list(existing.values())
    active_goal_id = str(
        (state.get('global_loop_state') or {}).get('active_goal_id') or state.get('active_goal_id') or ''
    )
    if active_goal_id and not any(item.get('goal_id') == active_goal_id for item in state['goals']):
        state.setdefault('global_loop_state', {})['active_goal_id'] = ''
    write_goal_state(project, state)
    return state


def upsert_goal_record(
    project: Path,
    *,
    goal: dict[str, Any] | None = None,
    goal_id: str = '',
    status: str = '',
    priority: int | None = None,
    resources: list[str] | None = None,
    depends_on: list[str] | None = None,
    progress: int | None = None,
) -> dict[str, Any]:
    state = load_goal_state(project)
    goal_payload = goal or resolve_goal(project, goal_id)
    if not goal_payload:
        goal_payload = {'goal_id': goal_id, 'goal': goal_id}
    goal_id = str(goal_payload.get('goal_id') or goal_id)
    goals = [dict(item) for item in state.get('goals') or [] if item.get('goal_id') != goal_id]
    existing = next((item for item in state.get('goals') or [] if item.get('goal_id') == goal_id), {})
    merged_goal = {
        **goal_payload,
        **existing,
        'goal_id': goal_id,
        'goal': goal_payload.get('goal') or existing.get('goal') or goal_id,
    }
    record = goal_record_from_payload(
        merged_goal,
        status=status or str(existing.get('status') or goal_payload.get('status') or 'paused'),
        priority=priority if priority is not None else existing.get('priority'),
        resources=resources if resources is not None else existing.get('resource_usage'),
        depends_on=depends_on if depends_on is not None else existing.get('depends_on'),
    )
    if progress is not None:
        record['progress'] = max(0, min(100, int(progress)))
    goals.append(record)
    state['goals'] = sorted(goals, key=lambda item: (-int(item.get('priority') or 0), str(item.get('goal_id') or '')))
    if record['status'] == 'active':
        for item in state['goals']:
            if item.get('goal_id') != goal_id and item.get('status') == 'active':
                item['status'] = 'paused'
        state.setdefault('global_loop_state', {})['active_goal_id'] = goal_id
    write_goal_state(project, state)
    return record


def set_goal_status(project: Path, goal_id: str, status: str) -> dict[str, Any]:
    if status not in GOAL_STATUSES:
        raise SystemExit(f'Unsupported goal status: {status}')
    state = load_goal_state(project)
    goal = _goal_map(state).get(goal_id)
    if not goal:
        upsert_goal_record(project, goal_id=goal_id, status=status)
        state = load_goal_state(project)
        goal = _goal_map(state).get(goal_id)
    if not goal or str(goal.get('status') or '') == status:
        return state
    current_status = str(goal.get('status') or 'paused')
    op = 'set_status'
    if status == 'completed':
        op = 'set_completion'
    elif status == 'blocked':
        op = 'set_blocker'
    elif status == 'backlog':
        op = 'set_backlog'
    reason = f'user_goal_status_command:{current_status}->{status}'
    patch = build_state_patch(
        project,
        source='user',
        reason=reason,
        changes=[
            {
                'goal_id': goal_id,
                'op': op,
                'from': current_status,
                'to': status,
                'requires_explicit_reason': True,
                'reason': reason,
            }
        ],
    )
    apply_goal_state_patch_data(project, patch)
    return load_goal_state(project)


def update_goal_from_goal_loop(project: Path, goal_loop_report: dict[str, Any]) -> None:
    goal_id = str(goal_loop_report.get('goal_id') or '')
    if not goal_id:
        return None
    status = str(goal_loop_report.get('goal_status') or '')
    progress = int(float(goal_loop_report.get('progress_score') or 0.0) * 100)
    state = load_goal_state(project)
    goal = _goal_map(state).get(goal_id)
    if not goal:
        upsert_goal_record(project, goal_id=goal_id, status='paused', progress=progress)
        state = load_goal_state(project)
        goal = _goal_map(state).get(goal_id)
    changes: list[dict[str, Any]] = [
        {
            'goal_id': goal_id,
            'op': 'set_progress',
            'from': goal.get('progress') if goal else '',
            'to': progress,
            'reason': 'goal_loop_progress_update',
        }
    ]
    current_status = str((goal or {}).get('status') or 'paused')
    if status == 'completed' and current_status != 'completed':
        changes.append(
            {
                'goal_id': goal_id,
                'op': 'set_completion',
                'from': current_status,
                'to': 'completed',
                'requires_explicit_reason': True,
                'reason': 'parent_aggregation_completed_goal',
            }
        )
    elif status == 'blocked' and current_status != 'blocked':
        changes.append(
            {
                'goal_id': goal_id,
                'op': 'set_blocker',
                'from': current_status,
                'to': 'blocked',
                'requires_explicit_reason': True,
                'reason': 'goal_loop_blocked',
            }
        )
    elif status == 'degraded' and current_status == 'active':
        changes.append(
            {
                'goal_id': goal_id,
                'op': 'set_status',
                'from': 'active',
                'to': 'paused',
                'requires_explicit_reason': True,
                'reason': 'goal_loop_waiting_human',
            }
        )
    patch = build_state_patch(project, source='goal_loop', reason='goal_loop_result', changes=changes)
    patch_path = (
        project / '.zoo-agent' / 'runs' / str(goal_loop_report.get('run_id') or 'unknown') / 'goal-state-patch.json'
    )
    write_json(patch_path, patch)
    result = apply_goal_state_patch_data(project, patch)
    return {'patch_path': str(patch_path), **result.get('paths', {})}


def render_report(project: Path, state: dict[str, Any]) -> dict[str, Any]:
    return {
        'status': 'ok',
        'workspace': str(project),
        'goal_state_path': str(state_paths(project)[0]),
        'goal_count': len(state.get('goals') or []),
        'active_goal_id': (state.get('global_loop_state') or {}).get('active_goal_id') or '',
        'state': state,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Manage multi-goal runtime state.')
    parser.add_argument('action', choices=['sync', 'list', 'upsert', 'pause', 'resume', 'complete', 'backlog', 'block'])
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--priority', type=int, default=None)
    parser.add_argument('--resource', action='append', default=[])
    parser.add_argument('--depends-on', action='append', default=[])
    parser.add_argument('--progress', type=int, default=None)
    args = parser.parse_args()
    project = project_root(args.workspace)
    if args.action == 'sync':
        state = sync_goals(project)
    elif args.action == 'list':
        state = load_goal_state(project)
        write_goal_state(project, state)
    elif args.action == 'upsert':
        if not args.goal_id:
            raise SystemExit('--goal-id is required for upsert')
        upsert_goal_record(
            project,
            goal_id=safe_name(args.goal_id),
            priority=args.priority,
            resources=args.resource,
            depends_on=args.depends_on,
            progress=args.progress,
        )
        state = load_goal_state(project)
    else:
        if not args.goal_id:
            raise SystemExit('--goal-id is required')
        status_map = {
            'pause': 'paused',
            'resume': 'active',
            'complete': 'completed',
            'backlog': 'backlog',
            'block': 'blocked',
        }
        state = set_goal_status(project, safe_name(args.goal_id), status_map[args.action])
    report = render_report(project, state)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
