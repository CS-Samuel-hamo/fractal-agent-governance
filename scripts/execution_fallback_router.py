#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FALLBACK_CHAIN = ['retry_codex', 'split_execution', 'reduce_scope_execution', 'dry_run_mode', 'escalate_to_planner']


def fallback_decision(
    model: dict[str, Any],
    *,
    retry_available: bool,
    split_available: bool,
    fallback_history: list[str] | None = None,
) -> dict[str, Any]:
    history = fallback_history or []
    status = str(model.get('execution_status') or '')
    if status == 'success':
        action = 'complete'
    elif retry_available and 'retry_codex' not in history:
        action = 'retry_codex'
    elif split_available and 'split_execution' not in history:
        action = 'split_execution'
    elif split_available and 'reduce_scope_execution' not in history:
        action = 'reduce_scope_execution'
    elif 'dry_run_mode' not in history:
        action = 'dry_run_mode'
    else:
        action = 'escalate_to_planner'
    return {
        'action': action,
        'fallback_chain': FALLBACK_CHAIN,
        'fallback_history': history,
        'blocked_allowed': action == 'escalate_to_planner',
        'reason': 'fallback_selected_after_execution_failure' if action != 'complete' else 'execution_succeeded',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Route failed executor attempts through the fallback chain.')
    parser.add_argument('--model', required=True)
    parser.add_argument('--retry-available', action='store_true')
    parser.add_argument('--split-available', action='store_true')
    parser.add_argument('--history', action='append', default=[])
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    model = json.loads(Path(args.model).resolve().read_text(encoding='utf-8-sig'))
    payload = fallback_decision(model, retry_available=args.retry_available, split_available=args.split_available, fallback_history=args.history)
    if args.output:
        path = Path(args.output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
