#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from goal_scheduler import schedule_goals  # noqa: E402
from goal_state_manager import apply_goal_state_patch_data, build_state_patch, load_goal_state  # noqa: E402
from filter_system_goals import filter_goals  # noqa: E402
from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


def normalize_backend_health(raw: str) -> str:
    value = str(raw or '').strip().lower()
    if value in {'healthy', 'health', 'ok'}:
        return 'healthy'
    if value in {'healthy_with_warnings', 'warning', 'warnings', 'degraded'}:
        return 'warning'
    if value in {'unhealthy', 'failed', 'fail', 'blocked'}:
        return 'unhealthy'
    return 'unknown'


def detect_backend_health(project: Path, explicit: str = '') -> str:
    if explicit:
        return normalize_backend_health(explicit)
    profile = load_json(project / '.zoo-agent' / 'backend' / 'codex-backend-profile.json')
    for key in ['health_status', 'health_verdict', 'verdict']:
        if profile.get(key):
            return normalize_backend_health(str(profile.get(key)))
    full = load_json(project / '.zoo-agent' / 'backend' / 'codex-health-full.json')
    if full.get('health_verdict') or full.get('verdict'):
        return normalize_backend_health(str(full.get('health_verdict') or full.get('verdict')))
    return 'unknown'


def system_pressure(state: dict[str, Any], *, conflicts: list[dict[str, Any]], backend_health: str) -> float:
    production_goal_ids = {str(item.get('goal_id')) for item in filter_goals(state).get('eligible_goals') or []}
    goals = [item for item in state.get('goals') or [] if item.get('goal_id') in production_goal_ids]
    active = len([item for item in goals if item.get('status') == 'active'])
    paused = len([item for item in goals if item.get('status') == 'paused'])
    backlog = len([item for item in goals if item.get('status') == 'backlog'])
    critical = len([item for item in conflicts if item.get('severity') == 'critical'])
    pressure = min(1.0, (active * 0.15) + (paused * 0.05) + (backlog * 0.08) + (critical * 0.35))
    if backend_health == 'unhealthy':
        pressure = max(pressure, 0.75)
    return round(pressure, 3)


def loop_patch(field: str, value: Any, reason: str) -> dict[str, Any]:
    return {'goal_id': '', 'op': 'set_loop_status', 'field': field, 'to': value, 'reason': reason}


def write_and_apply_patch(project: Path, *, reason: str, changes: list[dict[str, Any]], filename: str) -> dict[str, Any]:
    if not changes:
        return {}
    patch = build_state_patch(project, source='global_loop', reason=reason, changes=changes)
    patch_path = project / '.zoo-agent' / 'goal' / filename
    write_json(patch_path, patch)
    result = apply_goal_state_patch_data(project, patch)
    return {'patch_path': str(patch_path), **result.get('paths', {})}


def run_global_loop(
    project: Path,
    *,
    max_iterations: int = 100,
    max_continuous_goal_iterations: int = 3,
    backend_health: str = '',
    advance: bool = True,
) -> dict[str, Any]:
    state = load_goal_state(project)
    loop = state.setdefault('global_loop_state', {})
    current_iteration = int(loop.get('global_iteration') or loop.get('iteration') or 0)
    next_iteration = current_iteration + 1 if advance else current_iteration
    pre_patch_paths = write_and_apply_patch(
        project,
        reason='global_loop_iteration_update',
        filename='global-loop-iteration-state-patch.json',
        changes=[
            loop_patch('global_iteration', next_iteration, 'global_loop_iteration_update'),
            loop_patch('iteration', next_iteration, 'global_loop_iteration_update'),
            loop_patch('max_iterations', int(max_iterations), 'global_loop_iteration_update'),
        ],
    )

    health = detect_backend_health(project, backend_health)
    schedule = schedule_goals(
        project,
        max_continuous_iterations=max_continuous_goal_iterations,
        backend_health='unhealthy' if health == 'unhealthy' else health,
        single_goal_mode=True,
        apply_conflicts=True,
    )
    state = load_goal_state(project)
    loop = state.setdefault('global_loop_state', {})
    conflicts = (schedule.get('conflict_report') or {}).get('conflicts') or []
    pressure = system_pressure(state, conflicts=conflicts, backend_health=health)
    production_goal_ids = {str(item.get('goal_id')) for item in filter_goals(state).get('eligible_goals') or []}
    production_goals = [item for item in state.get('goals') or [] if item.get('goal_id') in production_goal_ids]
    completed_goals = [str(item.get('goal_id')) for item in production_goals if item.get('status') == 'completed']
    paused_goals = [str(item.get('goal_id')) for item in production_goals if item.get('status') == 'paused']
    backlog_goals = [str(item.get('goal_id')) for item in production_goals if item.get('status') == 'backlog']
    active_goal = str(loop.get('active_goal_id') or schedule.get('active_goal_id') or '')

    if production_goals and len(completed_goals) == len(production_goals):
        system_status = 'converged'
    elif next_iteration >= int(loop.get('max_iterations') or max_iterations):
        system_status = 'paused'
    elif health == 'unhealthy':
        system_status = 'degraded'
    elif pressure >= 0.7:
        system_status = 'degraded'
    else:
        system_status = str(loop.get('system_status') or schedule.get('system_status') or 'active')

    post_changes = [
        loop_patch('global_iteration', next_iteration, 'global_loop_status_update'),
        loop_patch('iteration', next_iteration, 'global_loop_status_update'),
        loop_patch('active_goal', active_goal, 'global_loop_status_update'),
        loop_patch('active_goal_id', active_goal, 'global_loop_status_update'),
        loop_patch('paused_goals', paused_goals, 'global_loop_status_update'),
        loop_patch('backlog_goals', backlog_goals, 'global_loop_status_update'),
        loop_patch('completed_goals', completed_goals, 'global_loop_status_update'),
        loop_patch('system_pressure', pressure, 'global_loop_status_update'),
        loop_patch('backend_health', health, 'global_loop_status_update'),
        loop_patch('system_status', system_status, 'global_loop_status_update'),
        loop_patch('actual_execution_frozen', bool(schedule.get('actual_execution_frozen') or health == 'unhealthy'), 'global_loop_status_update'),
        loop_patch('single_goal_mode', True, 'global_loop_status_update'),
        loop_patch('next_action', 'continue_active_goal' if active_goal and system_status == 'active' else 'human_or_scheduler_decision', 'global_loop_status_update'),
    ]
    if system_status in {'converged', 'paused', 'degraded'} and not active_goal:
        post_changes.extend(
            [
                loop_patch('active_goal_id', '', 'global_loop_no_active_goal'),
                loop_patch('active_goal', '', 'global_loop_no_active_goal'),
            ]
        )
    post_patch_paths = write_and_apply_patch(
        project,
        reason='global_loop_status_update',
        filename='global-loop-state-patch.json',
        changes=post_changes,
    )
    state = load_goal_state(project)
    loop = state.setdefault('global_loop_state', {})

    report = {
        'schema_version': '1.0',
        'generated_by': 'global_loop_engine.py',
        'generated_at': utc_now(),
        'workspace': str(project),
        'global_iteration': next_iteration,
        'max_iterations': loop.get('max_iterations'),
        'active_goal': loop.get('active_goal') or '',
        'paused_goals': paused_goals,
        'backlog_goals': backlog_goals,
        'completed_goals': completed_goals,
        'system_pressure': pressure,
        'backend_health': health,
        'system_status': system_status,
        'actual_execution_frozen': bool(loop.get('actual_execution_frozen')),
        'single_goal_mode': True,
        'schedule': schedule,
        'paths': {
            'goal_state': str(project / '.zoo-agent' / 'goal' / 'goal_state.json'),
            'global_loop_state': str(project / '.zoo-agent' / 'goal' / 'global-loop-state.json'),
            'goal_schedule': str(project / '.zoo-agent' / 'goal' / 'goal-schedule.json'),
            'iteration_state_patch': pre_patch_paths.get('patch_path', ''),
            'global_loop_state_patch': post_patch_paths.get('patch_path', ''),
        },
    }
    write_json(project / '.zoo-agent' / 'goal' / 'global-loop-state.json', report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Run global multi-goal loop scheduling and convergence control.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--max-iterations', type=int, default=100)
    parser.add_argument('--max-continuous-goal-iterations', type=int, default=3)
    parser.add_argument('--backend-health', default='')
    parser.add_argument('--no-advance', action='store_true')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = run_global_loop(
        project,
        max_iterations=args.max_iterations,
        max_continuous_goal_iterations=args.max_continuous_goal_iterations,
        backend_health=args.backend_health,
        advance=not args.no_advance,
    )
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
