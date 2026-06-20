#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def score_execution_health(models: list[dict[str, Any]]) -> dict[str, Any]:
    if not models:
        return {
            'score': 0.5,
            'execution_mode': 'single_actual_allowed',
            'parallel_allowed': False,
            'reason': 'no_execution_history',
            'stats': {},
        }
    total = len(models)
    success = sum(1 for item in models if item.get('execution_status') == 'success')
    timeout = sum(1 for item in models if item.get('execution_status') == 'timeout')
    partial = sum(1 for item in models if item.get('execution_status') == 'partial')
    avg_confidence = sum(float(item.get('confidence') or 0.0) for item in models) / total
    latencies = []
    for item in models:
        try:
            latencies.append(float(item.get('execution_time') or 0.0))
        except (TypeError, ValueError):
            pass
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    latency_penalty = min(0.2, avg_latency / 1800.0)
    score = (
        0.45 * (success / total)
        + 0.25 * avg_confidence
        + 0.15 * (1.0 - timeout / total)
        + 0.15 * (1.0 - partial / total)
        - latency_penalty
    )
    score = max(0.0, min(1.0, round(score, 4)))
    if score < 0.3:
        mode = 'dry_run_only'
    elif score < 0.5:
        mode = 'single_actual_only'
    else:
        mode = 'full_execution_allowed'
    return {
        'score': score,
        'execution_mode': mode,
        'parallel_allowed': score >= 0.5,
        'reason': 'score_below_parallel_threshold' if score < 0.5 else 'score_allows_parallel',
        'stats': {
            'total': total,
            'success_rate': round(success / total, 4),
            'timeout_rate': round(timeout / total, 4),
            'partial_rate': round(partial / total, 4),
            'avg_confidence': round(avg_confidence, 4),
            'avg_latency_seconds': round(avg_latency, 3),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Score executor health from execution result models.')
    parser.add_argument('--models-json', required=True)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    payload = json.loads(Path(args.models_json).resolve().read_text(encoding='utf-8-sig'))
    models = payload if isinstance(payload, list) else payload.get('models') or []
    result = score_execution_health(models)
    if args.output:
        path = Path(args.output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
