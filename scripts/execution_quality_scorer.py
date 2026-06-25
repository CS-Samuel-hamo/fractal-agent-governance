#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def _avg(values: list[float], default: float = 0.0) -> float:
    return round(sum(values) / len(values), 3) if values else default


def detect_false_success(execution: dict[str, Any], final_result: dict[str, Any]) -> bool:
    verdict = str(final_result.get('final_verdict') or '').upper()
    if verdict not in {'COMPLETED', 'DRY_RUN_COMPLETE'}:
        return False
    leaves = execution.get('leaf_results') or []
    if not leaves:
        return verdict == 'COMPLETED'
    outcomes = [str(item.get('delivery_outcome') or '').lower() for item in leaves]
    if verdict == 'COMPLETED' and not any(item in {'delivered', 'no_op_with_evidence'} for item in outcomes):
        return True
    if any(item in {'blocked', 'unsafe', 'no_delivery'} for item in outcomes) and verdict == 'COMPLETED':
        return True
    return False


def score_execution_quality(
    *,
    execution: dict[str, Any],
    final_result: dict[str, Any],
    failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failure = failure or {}
    leaves = execution.get('leaf_results') or []
    outcomes = [str(item.get('delivery_outcome') or '').lower() for item in leaves]
    models = [item.get('execution_model') for item in leaves if isinstance(item.get('execution_model'), dict)]
    confidences = [float(item.get('confidence') or 0.0) for item in models]
    if not confidences:
        confidences = [float(item.get('confidence') or 0.0) for item in leaves if item.get('confidence') is not None]
    if outcomes and all(item == 'dry_run_only' for item in outcomes):
        confidences = [0.75]

    delivered = sum(1 for item in outcomes if item in {'delivered', 'no_op_with_evidence'})
    dry_run = sum(1 for item in outcomes if item == 'dry_run_only')
    blocked = sum(1 for item in outcomes if item in {'blocked', 'unsafe'})
    no_delivery = sum(1 for item in outcomes if item == 'no_delivery')
    total = max(len(outcomes), 1)

    delivery_score = (delivered + 0.7 * dry_run) / total
    confidence_score = _avg(confidences, 0.65 if dry_run else 0.0)
    failure_type = str(failure.get('failure_type') or 'none')
    failure_penalty = {
        'none': 0.0,
        'partial': 0.2,
        'no_delivery': 0.35,
        'timeout': 0.45,
        'wrong_output': 0.5,
    }.get(failure_type, 0.4)
    false_success = detect_false_success(execution, final_result)
    false_success_penalty = 0.6 if false_success else 0.0
    execution_quality_score = _clamp(
        0.55 * delivery_score + 0.45 * confidence_score - failure_penalty - false_success_penalty
    )

    backend_statuses = []
    for leaf in leaves:
        status = str(leaf.get('backend_status') or '').lower()
        if status:
            backend_statuses.append(status)
    backend_failures = sum(
        1
        for status in backend_statuses
        if status in {'timeout', 'failed', 'exception', 'spawn_failed', 'no_output_timeout'}
    )
    backend_behavior_score = _clamp(1.0 - backend_failures / max(len(backend_statuses), 1))

    return {
        'execution_quality_score': execution_quality_score,
        'success_confidence': _clamp(confidence_score if not false_success else min(confidence_score, 0.25)),
        'backend_behavior_score': backend_behavior_score,
        'false_success_detected': false_success,
        'partial_completion_detected': failure_type == 'partial'
        or any(str((model or {}).get('execution_status') or '') == 'partial' for model in models),
        'delivery_counts': {
            'delivered': delivered,
            'dry_run_only': dry_run,
            'blocked': blocked,
            'no_delivery': no_delivery,
            'total': total,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Score internal execution quality from pipeline evidence.')
    parser.add_argument('--execution-result', required=True)
    parser.add_argument('--final-result', required=True)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    payload = score_execution_quality(
        execution=load_json(Path(args.execution_result).resolve()),
        final_result=load_json(Path(args.final_result).resolve()),
    )
    if args.output:
        path = Path(args.output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
