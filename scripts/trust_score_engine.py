#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def _confidence(score: float) -> str:
    if score >= 0.78:
        return 'high'
    if score >= 0.5:
        return 'medium'
    return 'low'


def _history(project: Path) -> list[dict[str, Any]]:
    payload = load_json(project / '.zoo-agent' / 'eval' / 'invisible_eval_history.json')
    rows = payload.get('history') if isinstance(payload.get('history'), list) else []
    return [item for item in rows if isinstance(item, dict)]


def build_trust_score(project: Path, eval_payload: dict[str, Any], impact: dict[str, Any]) -> dict[str, Any]:
    history = _history(project)[-20:]
    current_quality = float(eval_payload.get('execution_quality_score') or 0.0)
    backend_score = float(eval_payload.get('backend_behavior_score') or 0.0)
    false_success_penalty = 0.25 if eval_payload.get('false_success_detected') else 0.0
    fallback_frequency = 0.0
    if history:
        fallback_frequency = sum(1 for item in history if str(item.get('recommended_internal_action') or 'none') not in {'', 'none'}) / len(history)
    failure_history = 0.0
    if history:
        failure_history = sum(1 for item in history if str(item.get('failure_type') or 'none') != 'none') / len(history)
    impact_penalty = 0.0
    if impact.get('cross_module_risk') == 'medium':
        impact_penalty += 0.08
    if impact.get('backward_compatibility') in {'needs_review', 'unknown_without_tests'}:
        impact_penalty += 0.12
    trust_score = _clamp(
        0.5 * current_quality
        + 0.25 * backend_score
        + 0.15 * (1.0 - fallback_frequency)
        + 0.1 * (1.0 - failure_history)
        - false_success_penalty
        - impact_penalty
    )
    reasoning = (
        f"Trust is {_confidence(trust_score)} because the latest run scored {current_quality:.2f}, "
        f"recent recovery frequency is {fallback_frequency:.2f}, and impact risk is {impact.get('cross_module_risk', 'unknown')}."
    )
    return {
        'schema_version': '1.0',
        'generated_by': 'trust_score_engine.py',
        'generated_at': utc_now(),
        'run_id': eval_payload.get('run_id', ''),
        'trust_score': trust_score,
        'confidence_level': _confidence(trust_score),
        'reasoning': reasoning,
        'inputs': {
            'execution_success_rate': current_quality,
            'fallback_frequency': round(fallback_frequency, 3),
            'failure_history': round(failure_history, 3),
            'diff_stability': 1.0 if not eval_payload.get('false_success_detected') else 0.0,
            'backend_reliability': backend_score,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Compute a human-readable trust score for the latest run.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--eval', required=True)
    parser.add_argument('--impact', required=True)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_trust_score(project, load_json(Path(args.eval).resolve()), load_json(Path(args.impact).resolve()))
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'trust' / 'trust_score.json'
    write_json(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
