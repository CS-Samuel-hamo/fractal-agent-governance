#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, write_json  # noqa: E402


INTERNAL_TERMS = [
    'eval',
    'governance',
    'planner',
    'verifier',
    'scheduler',
    'backend internals',
    'policy internals',
]
UNSAFE_TERMS = ['git push', 'git merge', 'production deploy', 'delete user files', 'destructive operation']
SENSITIVE_TERMS = ['api key', 'token=', 'password=', 'private key']


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'session_dogfood'


def _read_json(path: Path) -> dict[str, Any]:
    return load_json(path)


def _scan_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def _scenario_map(trace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(run.get('scenario') or ''): run
        for run in trace.get('runs') or []
        if isinstance(run, dict)
    }


def _all_steps(trace: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in trace.get('runs') or []:
        if not isinstance(run, dict):
            continue
        scenario = str(run.get('scenario') or '')
        for step in run.get('steps') or []:
            if isinstance(step, dict):
                rows.append({'scenario': scenario, **step})
    return rows


def evaluate_trace(trace: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    scenarios = _scenario_map(trace)
    steps = _all_steps(trace)
    if not scenarios:
        failed.append('missing_dogfood_scenarios')
    for required in ['normal_session', 'undo', 'resume', 'needs_attention', 'no_delivery', 'budget']:
        run = scenarios.get(required)
        if not run:
            failed.append(f'missing_scenario:{required}')
        elif run.get('scenario_result') != 'pass':
            failed.append(f'scenario_failed:{required}')

    selected_steps = [step for step in steps if str(step.get('selected_action') or '')]
    map_backed_ok = [
        step for step in selected_steps if step.get('selected_action_source') == 'project_map.next_actions'
    ]
    map_backed_score = round(len(map_backed_ok) / max(len(selected_steps), 1), 3)
    if selected_steps and map_backed_score < 1.0:
        failed.append('non_map_backed_action_detected')

    actual_like = [
        step
        for step in steps
        if step.get('execution_outcome') in {'delivered', 'no_delivery', 'paused'}
        and step.get('scenario') != 'budget'
        and str(step.get('command') or '') not in {'agent stop', 'agent undo', 'agent status'}
    ]
    missing_checkpoint = [
        step for step in actual_like if not bool(step.get('checkpoint_created'))
    ]
    if missing_checkpoint:
        failed.append('missing_checkpoint_before_execution')

    cockpit_steps = [step for step in steps if step.get('scenario') not in {'needs_attention'} or step.get('cockpit_synced')]
    cockpit_ok = [step for step in cockpit_steps if step.get('cockpit_synced')]
    cockpit_sync_score = round(len(cockpit_ok) / max(len(cockpit_steps), 1), 3)
    if cockpit_sync_score < 0.85:
        failed.append('cockpit_sync_below_threshold')

    digest_ok = [step for step in steps if step.get('digest_updated')]
    if steps and len(digest_ok) < len(steps):
        failed.append('digest_not_updated_every_step')

    resume_run = scenarios.get('resume') or {}
    resume_reliability_score = 1.0 if resume_run.get('scenario_result') == 'pass' else 0.0
    undo_run = scenarios.get('undo') or {}
    undo_reliability_score = 1.0 if undo_run.get('scenario_result') == 'pass' else 0.0

    attention_runs = [scenarios.get('needs_attention') or {}, scenarios.get('no_delivery') or {}]
    attention_ok = [run for run in attention_runs if run.get('scenario_result') == 'pass']
    attention_handling_score = round(len(attention_ok) / max(len(attention_runs), 1), 3)
    if attention_handling_score < 1.0:
        failed.append('attention_handling_failed')

    unsafe_behavior = False
    for step in steps:
        text = _scan_text(step)
        if any(term in text for term in UNSAFE_TERMS):
            unsafe_behavior = True
        if step.get('scenario') == 'needs_attention' and step.get('execution_outcome') == 'delivered':
            unsafe_behavior = True
            failed.append('blocked_zone_executed')
        if step.get('session_status_after') == 'failed':
            failed.append('session_failed')
    if unsafe_behavior:
        failed.append('unsafe_behavior_detected')

    content_text = _scan_text(trace)
    internal_leakage = any(term in content_text for term in INTERNAL_TERMS)
    sensitive_leakage = any(term in content_text for term in SENSITIVE_TERMS)
    if internal_leakage:
        failed.append('internal_leakage_detected')
    if sensitive_leakage:
        failed.append('sensitive_content_detected')

    scenario_pass_rate = round(
        sum(1 for run in scenarios.values() if run.get('scenario_result') == 'pass') / max(len(scenarios), 1),
        3,
    )
    session_reliability_score = round(
        (
            scenario_pass_rate
            + map_backed_score
            + cockpit_sync_score
            + resume_reliability_score
            + undo_reliability_score
            + attention_handling_score
        )
        / 6,
        3,
    )

    recommendation = 'pass'
    if unsafe_behavior or internal_leakage or sensitive_leakage:
        recommendation = 'fail'
    elif failed:
        recommendation = 'fix_before_096'
    elif (
        session_reliability_score < 0.90
        or map_backed_score < 1.0
        or resume_reliability_score < 0.85
        or undo_reliability_score < 0.85
        or cockpit_sync_score < 0.85
    ):
        recommendation = 'fix_before_096'

    return {
        'session_reliability_score': session_reliability_score,
        'resume_reliability_score': resume_reliability_score,
        'undo_reliability_score': undo_reliability_score,
        'cockpit_sync_score': cockpit_sync_score,
        'map_backed_execution_score': map_backed_score,
        'attention_handling_score': attention_handling_score,
        'internal_leakage_detected': internal_leakage,
        'unsafe_behavior_detected': unsafe_behavior,
        'failed_checks': sorted(set(failed)),
        'recommendation': recommendation,
    }


def run_gate(project: Path, *, trace_path: Path | None = None) -> dict[str, Any]:
    path = trace_path or dogfood_dir(project) / 'session_dogfood_trace.json'
    trace = _read_json(path)
    report = {
        'schema_version': '1.0',
        'generated_by': 'session_reliability_gate.py',
        **evaluate_trace(trace),
    }
    write_json(dogfood_dir(project) / 'session_reliability_report.json', report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Check long-running session dogfood reliability.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--trace', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    trace_path = Path(args.trace).resolve() if args.trace else None
    report = run_gate(project, trace_path=trace_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('recommendation') in {'pass', 'fix_before_096'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
