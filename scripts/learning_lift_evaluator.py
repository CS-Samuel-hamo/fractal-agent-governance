#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cross_project_store import load_store, store_dir  # noqa: E402
from runtime_common import load_json, project_root, write_json  # noqa: E402


READY = 'pass'
FIX = 'fix_before_098'
FAIL = 'fail'
PRIVACY_RE = re.compile(r'(SHOULD-NOT-BE-READ|FAKE_TOKEN_12345|sk-[A-Za-z0-9]{12,}|raw backend log that should not be stored|C:\\Users\\|D:\\AI_)', re.IGNORECASE)


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'learning_dogfood'


def ratio(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(1 for item in rows if item.get(key)) / len(rows), 3)


def privacy_violation(project: Path) -> tuple[bool, list[str]]:
    hits: list[str] = []
    for base in [dogfood_dir(project), store_dir(project)]:
        if not base.exists():
            continue
        for path in base.rglob('*'):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue
            if PRIVACY_RE.search(text):
                hits.append(path.relative_to(project).as_posix())
    return bool(hits), hits[:12]


def artifact_presence(project: Path) -> dict[str, bool]:
    return {
        'pattern_library': bool(load_store(project, 'pattern_library').get('patterns')),
        'release_templates': bool(load_store(project, 'release_templates').get('templates')),
        'worker_memory': bool(load_store(project, 'worker_memory').get('worker_performance')),
        'failure_taxonomy': bool(load_store(project, 'failure_taxonomy').get('failure_patterns')),
        'learning_insights': bool(load_store(project, 'learning_insights').get('insights')),
        'learning_feedback': (store_dir(project) / 'learning_feedback_applied.json').exists(),
    }


def evaluate_lift(project: Path, *, comparison_path: Path | None = None, output_path: Path | None = None) -> dict[str, Any]:
    comparison = load_json(comparison_path or dogfood_dir(project) / 'baseline_comparison.json')
    rows = [item for item in comparison.get('comparisons') or [] if isinstance(item, dict)]
    summary = comparison.get('summary') if isinstance(comparison.get('summary'), dict) else {}
    next_score = ratio(rows, 'next_action_improved')
    release_score = ratio(rows, 'release_sequence_improved')
    worker_score = ratio(rows, 'worker_preference_improved')
    failure_score = ratio(rows, 'failure_warning_added')
    safety_score = 1.0 if rows and all(item.get('safety_boundary_preserved') for item in rows) else 0.0
    privacy_bad, privacy_hits = privacy_violation(project)
    privacy_score = 0.0 if privacy_bad else 1.0
    negative = int(summary.get('projects_with_negative_lift') or 0) > 0 or any(item.get('negative_lift_detected') for item in rows)
    unsafe = safety_score < 1.0
    presence = artifact_presence(project)
    missing = [name for name, exists in presence.items() if not exists]
    learning_lift = round((next_score + release_score + worker_score + failure_score + privacy_score + safety_score) / 6, 3)
    failed_checks = []
    if next_score < 0.80:
        failed_checks.append('next_action_lift_below_threshold')
    if release_score < 0.80:
        failed_checks.append('release_readiness_lift_below_threshold')
    if worker_score < 0.75:
        failed_checks.append('worker_routing_lift_below_threshold')
    if failure_score < 0.75:
        failed_checks.append('failure_avoidance_lift_below_threshold')
    if privacy_score != 1.0:
        failed_checks.append('privacy_violation')
    if safety_score != 1.0:
        failed_checks.append('safety_boundary_violation')
    if negative:
        failed_checks.append('negative_learning_detected')
    if missing:
        failed_checks.append('missing_learning_artifacts:' + ','.join(missing))
    recommendation = READY
    if failed_checks:
        recommendation = FAIL if negative or unsafe or privacy_bad else FIX
    if learning_lift < 0.85 and recommendation == READY:
        recommendation = FIX
        failed_checks.append('learning_lift_below_threshold')
    payload = {
        'schema_version': '1.0',
        'generated_by': 'learning_lift_evaluator.py',
        'learning_lift_score': learning_lift,
        'next_action_lift_score': next_score,
        'release_readiness_lift_score': release_score,
        'worker_routing_lift_score': worker_score,
        'failure_avoidance_lift_score': failure_score,
        'privacy_score': privacy_score,
        'safety_preservation_score': safety_score,
        'negative_learning_detected': negative,
        'unsafe_learning_detected': unsafe,
        'privacy_violation_detected': privacy_bad,
        'failed_checks': failed_checks,
        'privacy_hits': privacy_hits,
        'recommendation': recommendation,
    }
    write_json(output_path or dogfood_dir(project) / 'learning_lift_report.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate cross-project learning lift.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--comparison', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = evaluate_lift(
        project,
        comparison_path=Path(args.comparison).resolve() if args.comparison else None,
        output_path=Path(args.output).resolve() if args.output else None,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('recommendation') == READY else 1


if __name__ == '__main__':
    raise SystemExit(main())
