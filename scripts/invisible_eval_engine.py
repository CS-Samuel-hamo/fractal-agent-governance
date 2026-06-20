#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from execution_quality_scorer import score_execution_quality
from failure_classifier import classify_failure_mode
from learning_signal_engine import collect_and_write_learning_signal
from runtime_common import load_json, project_root, utc_now, write_json
from runtime_governance_engine import decide_internal_action
from runtime_health_monitor import append_eval_history, build_health_report


def build_invisible_eval(
    *,
    project: Path,
    run_id: str,
    plan_path: Path,
    execution_path: Path,
    final_path: Path,
    stage_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = load_json(plan_path)
    execution = load_json(execution_path)
    final_result = load_json(final_path)
    failure = classify_failure_mode(execution=execution, final_result=final_result, stage_results=stage_results or {})
    scores = score_execution_quality(execution=execution, final_result=final_result, failure=failure)
    eval_payload = {
        'schema_version': '1.0',
        'generated_by': 'invisible_eval_engine.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'workspace': str(project),
        'trace_refs': {
            'plan_json': str(plan_path),
            'execution_result_json': str(execution_path),
            'final_result_json': str(final_path),
        },
        'execution_quality_score': scores['execution_quality_score'],
        'success_confidence': scores['success_confidence'],
        'failure_type': failure['failure_type'],
        'false_success_detected': scores['false_success_detected'],
        'backend_behavior_score': scores['backend_behavior_score'],
        'recommended_internal_action': 'none',
        'basis': {
            'failure_reason': failure.get('reason', ''),
            'delivery_counts': scores.get('delivery_counts', {}),
            'final_verdict': final_result.get('final_verdict', ''),
            'route': (plan.get('execution_plan') or {}).get('route', ''),
        },
    }
    governance = decide_internal_action(eval_payload)
    eval_payload['recommended_internal_action'] = governance['recommended_internal_action']
    return eval_payload


def run_invisible_eval(
    *,
    project: Path,
    run_id: str,
    plan_path: Path,
    execution_path: Path,
    final_path: Path,
    stage_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    eval_payload = build_invisible_eval(
        project=project,
        run_id=run_id,
        plan_path=plan_path,
        execution_path=execution_path,
        final_path=final_path,
        stage_results=stage_results,
    )
    run_eval_path = project / '.zoo-agent' / 'runs' / run_id / 'eval' / 'invisible_eval.json'
    latest_eval_path = project / '.zoo-agent' / 'eval' / 'invisible_eval.json'
    write_json(run_eval_path, eval_payload)
    write_json(latest_eval_path, eval_payload)

    governance = decide_internal_action(eval_payload)
    write_json(project / '.zoo-agent' / 'runs' / run_id / 'eval' / 'runtime_governance_decision.json', governance)
    write_json(project / '.zoo-agent' / 'eval' / 'runtime_governance_decision.json', governance)

    health = build_health_report(project, eval_payload)
    append_eval_history(project, eval_payload)
    write_json(project / '.zoo-agent' / 'eval' / 'runtime_health.json', health)

    learning = collect_and_write_learning_signal(project, eval_payload, governance)
    return {
        'status': 'ok',
        'run_id': run_id,
        'invisible_eval_json': str(latest_eval_path),
        'run_invisible_eval_json': str(run_eval_path),
        'governance_action': governance.get('recommended_internal_action', 'none'),
        'health_metrics': health.get('metrics', {}),
        'learning_signal_count': len(learning.get('signals') or []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Run internal invisible eval after pipeline execution.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--execution-result', required=True)
    parser.add_argument('--final-result', required=True)
    parser.add_argument('--stage-results', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    stage_results = load_json(Path(args.stage_results).resolve()) if args.stage_results else {}
    payload = run_invisible_eval(
        project=project,
        run_id=args.run_id,
        plan_path=Path(args.plan).resolve(),
        execution_path=Path(args.execution_result).resolve(),
        final_path=Path(args.final_result).resolve(),
        stage_results=stage_results,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
