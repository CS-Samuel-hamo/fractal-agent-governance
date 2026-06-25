#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from filter_system_goals import filter_goals
from goal_conflict_detector import apply_conflict_resolutions, detect_conflicts, write_conflict_report
from goal_priority_engine import dependency_blocked, rank_goals
from goal_state_manager import apply_goal_state_patch_data, build_state_patch, load_goal_state, sync_goals
from runtime_common import project_root, utc_now, write_json

BACKEND_UNHEALTHY = {'unhealthy', 'UNHEALTHY'}


def status_groups(goals: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        'paused_goals': [str(item.get('goal_id')) for item in goals if item.get('status') == 'paused'],
        'backlog_goals': [str(item.get('goal_id')) for item in goals if item.get('status') == 'backlog'],
        'completed_goals': [str(item.get('goal_id')) for item in goals if item.get('status') == 'completed'],
        'blocked_goals': [str(item.get('goal_id')) for item in goals if item.get('status') == 'blocked'],
    }


def eligible_goal_ids(state: dict[str, Any]) -> set[str]:
    goals = [dict(item) for item in state.get('goals') or []]
    goals_by_id = {str(item.get('goal_id')): item for item in goals}
    production_goal_ids = {str(item.get('goal_id')) for item in filter_goals(state)['eligible_goals']}
    eligible: set[str] = set()
    for goal in goals:
        goal_id = str(goal.get('goal_id') or '')
        if not goal_id:
            continue
        if goal_id not in production_goal_ids:
            continue
        if goal.get('status') in {'completed', 'blocked'}:
            continue
        if dependency_blocked(goal, goals_by_id):
            continue
        eligible.add(goal_id)
    return eligible


def pick_active_goal(state: dict[str, Any], *, max_continuous_iterations: int) -> tuple[str, bool]:
    active_goal_id = str((state.get('global_loop_state') or {}).get('active_goal_id') or '')
    goals_by_id = {str(item.get('goal_id')): item for item in state.get('goals') or []}
    eligible = eligible_goal_ids(state)
    if not eligible:
        return '', False
    current = goals_by_id.get(active_goal_id)
    skip_current = bool(
        current
        and active_goal_id in eligible
        and int(current.get('continuous_iterations') or 0) >= max_continuous_iterations
        and len(eligible) > 1
    )
    ranking = rank_goals(state)
    for item in ranking:
        goal_id = str(item.get('goal_id') or '')
        if goal_id not in eligible:
            continue
        if skip_current and goal_id == active_goal_id:
            continue
        return goal_id, skip_current
    return active_goal_id if active_goal_id in eligible else next(iter(sorted(eligible))), False


def loop_patch(field: str, value: Any, reason: str) -> dict[str, Any]:
    return {'goal_id': '', 'op': 'set_loop_status', 'field': field, 'to': value, 'reason': reason}


def write_and_apply_patch(
    project: Path, *, source: str, reason: str, changes: list[dict[str, Any]], filename: str
) -> dict[str, Any]:
    if not changes:
        return {}
    patch = build_state_patch(project, source=source, reason=reason, changes=changes)
    patch_path = project / '.zoo-agent' / 'goal' / filename
    write_json(patch_path, patch)
    result = apply_goal_state_patch_data(project, patch)
    return {'patch_path': str(patch_path), **result.get('paths', {})}


def schedule_goals(
    project: Path,
    *,
    max_continuous_iterations: int = 3,
    backend_health: str = '',
    single_goal_mode: bool = True,
    apply_conflicts: bool = True,
) -> dict[str, Any]:
    state = sync_goals(project)
    loop = state.setdefault('global_loop_state', {})
    patch_paths = write_and_apply_patch(
        project,
        source='scheduler',
        reason='scheduler_loop_metadata_update',
        filename='goal-scheduler-loop-state-patch.json',
        changes=[
            loop_patch('max_continuous_goal_iterations', max_continuous_iterations, 'scheduler_loop_metadata_update'),
            loop_patch('single_goal_mode', bool(single_goal_mode), 'scheduler_loop_metadata_update'),
            loop_patch(
                'backend_health',
                backend_health or loop.get('backend_health') or 'unknown',
                'scheduler_loop_metadata_update',
            ),
        ],
    )
    state = load_goal_state(project)

    goal_filter = filter_goals(state)
    conflict_report = detect_conflicts(project)
    if apply_conflicts:
        conflict_report = apply_conflict_resolutions(project, conflict_report)
        state = load_goal_state(project)
        loop = state.setdefault('global_loop_state', {})
        goal_filter = filter_goals(state)
    write_conflict_report(project, conflict_report)

    actual_execution_frozen = (backend_health or '').strip() in BACKEND_UNHEALTHY
    starvation_prevention_applied = False
    schedule_changes: list[dict[str, Any]] = []
    for excluded in goal_filter.get('excluded_goals') or []:
        goal_id = str(excluded.get('goal_id') or '')
        goal = next((item for item in state.get('goals') or [] if item.get('goal_id') == goal_id), {})
        if goal.get('status') == 'active':
            schedule_changes.append(
                {
                    'goal_id': goal_id,
                    'op': 'set_status',
                    'from': 'active',
                    'to': 'paused',
                    'requires_explicit_reason': True,
                    'reason': f'excluded_from_production_scheduler:{excluded.get("goal_type")}',
                }
            )
    if actual_execution_frozen:
        schedule_changes.extend(
            [
                {'goal_id': '', 'op': 'freeze_actual_execution', 'reason': f'backend_health_{backend_health}'},
                loop_patch('actual_execution_frozen', True, f'backend_health_{backend_health}'),
                loop_patch('system_status', 'degraded', f'backend_health_{backend_health}'),
            ]
        )
    else:
        selected_goal_id, starvation_prevention_applied = pick_active_goal(
            state,
            max_continuous_iterations=max(1, max_continuous_iterations),
        )
        goals = state.get('goals') or []
        production_goal_ids = {str(item.get('goal_id')) for item in goal_filter.get('eligible_goals') or []}
        for goal in goals:
            goal_id = str(goal.get('goal_id') or '')
            if not goal_id:
                continue
            if goal_id not in production_goal_ids:
                continue
            if goal.get('status') == 'completed':
                continue
            if goal_id == selected_goal_id:
                if goal.get('status') != 'active':
                    schedule_changes.append(
                        {
                            'goal_id': goal_id,
                            'op': 'set_status',
                            'from': goal.get('status') or 'paused',
                            'to': 'active',
                            'requires_explicit_reason': True,
                            'reason': 'scheduler_selected_goal',
                        }
                    )
            else:
                if goal.get('status') == 'active':
                    schedule_changes.append(
                        {
                            'goal_id': goal_id,
                            'op': 'set_status',
                            'from': 'active',
                            'to': 'paused',
                            'requires_explicit_reason': True,
                            'reason': 'scheduler_single_active_goal_mode',
                        }
                    )
        schedule_changes.extend(
            [
                loop_patch('active_goal_id', selected_goal_id, 'scheduler_selected_goal'),
                loop_patch('active_goal', selected_goal_id, 'scheduler_selected_goal'),
                loop_patch('actual_execution_frozen', False, 'scheduler_backend_allows_actual'),
                loop_patch('system_status', 'active' if selected_goal_id else 'converged', 'scheduler_selected_goal'),
            ]
        )

    production_goals = [
        item
        for item in state.get('goals') or []
        if item.get('goal_id') in {row.get('goal_id') for row in goal_filter.get('eligible_goals') or []}
    ]
    groups = status_groups(production_goals)
    if production_goals and len(groups['completed_goals']) == len(production_goals):
        schedule_changes.extend(
            [
                loop_patch('system_status', 'converged', 'all_goals_completed'),
                loop_patch('active_goal_id', '', 'all_goals_completed'),
                loop_patch('active_goal', '', 'all_goals_completed'),
            ]
        )
    elif any(item.get('severity') == 'critical' for item in conflict_report.get('conflicts') or []):
        schedule_changes.append(loop_patch('system_status', 'degraded', 'critical_conflict_detected'))

    schedule_patch_paths = write_and_apply_patch(
        project,
        source='scheduler',
        reason='scheduler_selection_result',
        filename='goal-scheduler-state-patch.json',
        changes=schedule_changes,
    )
    state = load_goal_state(project)
    final_filter = filter_goals(state)
    final_queue_ids = eligible_goal_ids(state)
    final_eligible_goals = [
        row for row in final_filter.get('eligible_goals') or [] if row.get('goal_id') in final_queue_ids
    ]
    final_production_goals = [
        item
        for item in state.get('goals') or []
        if item.get('goal_id') in {row.get('goal_id') for row in final_filter.get('eligible_goals') or []}
    ]
    groups = status_groups(final_production_goals)

    report = {
        'schema_version': '1.0',
        'generated_by': 'goal_scheduler.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'active_goal': (state.get('global_loop_state') or {}).get('active_goal_id') or '',
        'active_goal_id': (state.get('global_loop_state') or {}).get('active_goal_id') or '',
        'single_goal_mode': bool(single_goal_mode),
        'actual_execution_frozen': bool((state.get('global_loop_state') or {}).get('actual_execution_frozen')),
        'system_status': (state.get('global_loop_state') or {}).get('system_status') or 'active',
        'starvation_prevention_applied': starvation_prevention_applied,
        'max_continuous_goal_iterations': max_continuous_iterations,
        'ranking': rank_goals(state),
        'eligible_goals': final_eligible_goals,
        'production_goals': final_filter.get('eligible_goals') or [],
        'excluded_goals': final_filter.get('excluded_goals') or [],
        'exclusion_reason': final_filter.get('exclusion_reason') or {},
        'conflict_report': conflict_report,
        **status_groups(final_production_goals),
        'paths': {
            'goal_state': str(project / '.zoo-agent' / 'goal' / 'goal_state.json'),
            'goal_schedule': str(project / '.zoo-agent' / 'goal' / 'goal-schedule.json'),
            'goal_conflicts': str(project / '.zoo-agent' / 'goal' / 'goal-conflicts.json'),
            'metadata_state_patch': patch_paths.get('patch_path', ''),
            'schedule_state_patch': schedule_patch_paths.get('patch_path', ''),
        },
    }
    write_json(project / '.zoo-agent' / 'goal' / 'goal-schedule.json', report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Schedule multi-goal runtime state with priority, fairness, and conflicts.'
    )
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--max-continuous-iterations', type=int, default=3)
    parser.add_argument('--backend-health', default='')
    parser.add_argument(
        '--multi-goal-mode',
        action='store_true',
        help='Allow scheduler to consider the full goal set while still activating one goal.',
    )
    parser.add_argument('--no-apply-conflicts', action='store_true')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = schedule_goals(
        project,
        max_continuous_iterations=args.max_continuous_iterations,
        backend_health=args.backend_health,
        single_goal_mode=not args.multi_goal_mode,
        apply_conflicts=not args.no_apply_conflicts,
    )
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
