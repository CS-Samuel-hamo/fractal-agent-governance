#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from runtime_common import utc_now


def build_learning_signal(eval_payload: dict[str, Any], governance_decision: dict[str, Any]) -> dict[str, Any]:
    return {
        'signal_id': f'signal-{eval_payload.get("run_id") or utc_now()}',
        'created_at': utc_now(),
        'run_id': eval_payload.get('run_id', ''),
        'failure_type': eval_payload.get('failure_type', 'none'),
        'execution_quality_score': eval_payload.get('execution_quality_score', 0.0),
        'success_confidence': eval_payload.get('success_confidence', 0.0),
        'backend_behavior_score': eval_payload.get('backend_behavior_score', 0.0),
        'false_success_detected': bool(eval_payload.get('false_success_detected')),
        'recommended_internal_action': governance_decision.get('recommended_internal_action', 'none'),
        'pattern_tags': [
            tag
            for tag in [
                'false_success' if eval_payload.get('false_success_detected') else '',
                str(eval_payload.get('failure_type') or ''),
                str(governance_decision.get('recommended_internal_action') or ''),
            ]
            if tag and tag != 'none'
        ],
    }
