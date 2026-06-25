#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def _load_history(project: Path) -> list[dict[str, Any]]:
    payload = load_json(project / '.zoo-agent' / 'eval' / 'invisible_eval_history.json')
    history = payload.get('history') if isinstance(payload.get('history'), list) else []
    return [item for item in history if isinstance(item, dict)]


def build_health_report(project: Path, eval_payload: dict[str, Any]) -> dict[str, Any]:
    history = _load_history(project)
    window = [*history[-49:], eval_payload]
    total = max(len(window), 1)
    false_successes = sum(1 for item in window if item.get('false_success_detected'))
    classified = sum(1 for item in window if str(item.get('failure_type') or 'none') != 'none')
    actions = [str(item.get('recommended_internal_action') or 'none') for item in window]
    stable = sum(1 for item in window if float(item.get('execution_quality_score') or 0.0) >= 0.6)
    backend_scores = [float(item.get('backend_behavior_score') or 0.0) for item in window]

    report = {
        'schema_version': '1.0',
        'generated_by': 'runtime_health_monitor.py',
        'generated_at': utc_now(),
        'run_id': eval_payload.get('run_id', ''),
        'metrics': {
            'eval_accuracy_score': _clamp(1.0 - false_successes / total),
            'false_success_detection_rate': _clamp(false_successes / total),
            'failure_classification_accuracy': _clamp(
                1.0 if classified or eval_payload.get('failure_type') == 'none' else 0.8
            ),
            'fallback_effectiveness': _clamp(1.0 - actions.count('escalate') / total),
            'runtime_stability_score': _clamp(stable / total),
            'backend_behavior_consistency': _clamp(sum(backend_scores) / max(len(backend_scores), 1)),
        },
        'sample_size': total,
    }
    return report


def append_eval_history(project: Path, eval_payload: dict[str, Any], *, limit: int = 200) -> None:
    path = project / '.zoo-agent' / 'eval' / 'invisible_eval_history.json'
    history = _load_history(project)
    history.append(eval_payload)
    write_json(
        path,
        {
            'schema_version': '1.0',
            'generated_by': 'runtime_health_monitor.py',
            'updated_at': utc_now(),
            'history': history[-limit:],
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='Update internal runtime health metrics from invisible eval history.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--eval', required=True)
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    eval_payload = load_json(Path(args.eval).resolve())
    report = build_health_report(project, eval_payload)
    append_eval_history(project, eval_payload)
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'eval' / 'runtime_health.json'
    write_json(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
