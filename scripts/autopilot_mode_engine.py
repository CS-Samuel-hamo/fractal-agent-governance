#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def normalize_mode(value: str | None) -> str:
    text = str(value or '').strip().lower()
    if text in {'preview', 'standard', 'autopilot'}:
        return text
    return 'standard'


def max_steps_for_mode(mode: str, requested: int = 0) -> int:
    if requested > 0:
        return requested
    if mode == 'autopilot':
        return 3
    return 1


def should_pause_after_result(final_result: dict[str, Any], execution: dict[str, Any]) -> tuple[bool, str]:
    verdict = str(final_result.get('final_verdict') or '')
    if verdict in {'BLOCKED', 'NO_DELIVERY', 'NEEDS_DELIVERY_VERIFICATION', 'PARTIAL'}:
        if verdict == 'NO_DELIVERY':
            return True, 'action did not produce a usable change'
        return True, 'action needs review before continuing'
    for leaf in execution.get('leaf_results') or []:
        status = str(leaf.get('execution_status') or '')
        outcome = str(leaf.get('delivery_outcome') or '')
        if status in {'timeout', 'failed', 'partial'}:
            return True, 'worker could not complete the action'
        if outcome in {'blocked', 'unsafe', 'no_delivery'}:
            return True, 'action needs review before continuing'
    return False, ''
