#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import project_root
from session_state_store import load_session_history, load_session_state


DEFAULT_BUDGET = {
    'max_steps': 5,
    'max_minutes': 30,
    'max_failures': 1,
    'max_no_delivery': 1,
    'max_changed_files_per_step': 10,
    'max_consecutive_guarded_actions': 1,
}


def normalize_budget(overrides: dict[str, Any] | None = None) -> dict[str, int]:
    payload = {key: int(value) for key, value in DEFAULT_BUDGET.items()}
    for key, value in (overrides or {}).items():
        if key in payload and value is not None:
            payload[key] = max(0, int(value))
    return payload


def budget_decision(state: dict[str, Any], history: dict[str, Any], budget: dict[str, int] | None = None) -> dict[str, Any]:
    budget = normalize_budget(budget)
    steps = [item for item in history.get('steps') or [] if isinstance(item, dict)]
    failures = len([item for item in steps if item.get('outcome') in {'failed', 'blocked', 'timeout'}])
    no_delivery = len([item for item in steps if item.get('outcome') == 'no_delivery'])
    guarded_tail = 0
    for item in reversed(steps):
        if item.get('trust_zone') == 'guarded':
            guarded_tail += 1
        else:
            break
    current_step = int(state.get('current_step') or 0)
    changed_too_many = any(len(item.get('changed_files') or []) > budget['max_changed_files_per_step'] for item in steps[-1:])
    reasons: list[str] = []
    status = 'ok'
    if budget['max_steps'] and current_step >= budget['max_steps']:
        status = 'paused'
        reasons.append('step_budget_reached')
    if failures > budget['max_failures']:
        status = 'needs_attention'
        reasons.append('failure_budget_exceeded')
    if no_delivery > budget['max_no_delivery']:
        status = 'needs_attention'
        reasons.append('no_delivery_budget_exceeded')
    if guarded_tail > budget['max_consecutive_guarded_actions']:
        status = 'paused'
        reasons.append('guarded_action_budget_reached')
    if changed_too_many:
        status = 'paused'
        reasons.append('changed_file_budget_reached')
    return {
        'status': status,
        'reasons': reasons,
        'budget': budget,
        'failure_count': failures,
        'no_delivery_count': no_delivery,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate long-running session budget.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    state, _ = load_session_state(project)
    history = load_session_history(project)
    print(json.dumps(budget_decision(state, history), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
