#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from goal_state_manager import load_goal_state, project_root  # noqa: E402


def dependency_blocked(goal: dict[str, Any], goals_by_id: dict[str, dict[str, Any]]) -> bool:
    for dep in goal.get('depends_on') or []:
        if goals_by_id.get(str(dep), {}).get('status') != 'completed':
            return True
    return False


def priority_score(goal: dict[str, Any], goals_by_id: dict[str, dict[str, Any]], *, active_goal_id: str = '') -> dict[str, Any]:
    status = str(goal.get('status') or 'paused')
    base = int(goal.get('priority') or 0)
    starvation = int(goal.get('starvation_count') or 0)
    continuous = int(goal.get('continuous_iterations') or 0)
    progress = int(goal.get('progress') or 0)
    blockers: list[str] = []
    score = base
    if status in {'completed', 'blocked'}:
        score -= 1000
        blockers.append(f'status_{status}')
    if dependency_blocked(goal, goals_by_id):
        score -= 500
        blockers.append('dependency_not_completed')
    if status == 'backlog':
        score -= 10
    if status == 'paused':
        score -= 3
    score += min(starvation * 8, 40)
    if str(goal.get('goal_id')) == active_goal_id:
        score -= max(continuous - 1, 0) * 15
    if 0 < progress < 100:
        score += 5
    return {
        'goal_id': goal.get('goal_id'),
        'score': score,
        'base_priority': base,
        'starvation_count': starvation,
        'continuous_iterations': continuous,
        'blocked': bool(blockers),
        'blockers': blockers,
    }


def rank_goals(state: dict[str, Any]) -> list[dict[str, Any]]:
    goals = [dict(item) for item in state.get('goals') or []]
    goals_by_id = {str(item.get('goal_id')): item for item in goals}
    active_goal_id = str((state.get('global_loop_state') or {}).get('active_goal_id') or '')
    scored = [priority_score(goal, goals_by_id, active_goal_id=active_goal_id) for goal in goals]
    return sorted(scored, key=lambda item: (-int(item.get('score') or 0), str(item.get('goal_id') or '')))


def main() -> int:
    parser = argparse.ArgumentParser(description='Rank goals for scheduling using priority and fairness.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    state = load_goal_state(project)
    ranking = rank_goals(state)
    print(json.dumps({'status': 'ok', 'workspace': str(project), 'ranking': ranking}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
