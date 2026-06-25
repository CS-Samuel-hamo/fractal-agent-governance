#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, write_json


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'learning_dogfood'


def list_changed(before: list[Any], after: list[Any]) -> bool:
    return [str(item) for item in before] != [str(item) for item in after]


def has_evidence(row: dict[str, Any]) -> bool:
    learning = row.get('learning_enabled') if isinstance(row.get('learning_enabled'), dict) else {}
    return bool(learning.get('learning_insights_used') and learning.get('evidence_backed_reasons'))


def safety_preserved(row: dict[str, Any]) -> bool:
    safety = row.get('safety') if isinstance(row.get('safety'), dict) else {}
    return all(
        bool(safety.get(key))
        for key in ['blocked_zone_respected', 'checkpoint_required', 'no_secret_saved', 'no_raw_source_saved']
    )


def compare_row(row: dict[str, Any]) -> dict[str, Any]:
    baseline = row.get('baseline') if isinstance(row.get('baseline'), dict) else {}
    learning = row.get('learning_enabled') if isinstance(row.get('learning_enabled'), dict) else {}
    evidence_backed = has_evidence(row)
    safe = safety_preserved(row)
    next_changed = list_changed(
        baseline.get('selected_next_actions') or [], learning.get('selected_next_actions') or []
    )
    release_changed = list_changed(baseline.get('release_sequence') or [], learning.get('release_sequence') or [])
    worker_changed = list_changed(baseline.get('worker_preferences') or [], learning.get('worker_preferences') or [])
    warning_added = len(learning.get('failure_warnings') or []) > len(baseline.get('failure_warnings') or [])
    unsupported = bool(learning.get('unsupported_next_action_selected'))
    blocked_promoted = bool(learning.get('blocked_zone_promoted_to_execution'))
    next_improved = bool(next_changed and evidence_backed and safe and not unsupported and not blocked_promoted)
    release_improved = bool(release_changed and evidence_backed and safe and not unsupported)
    worker_improved = bool(worker_changed and evidence_backed and safe)
    failure_improved = bool(warning_added and evidence_backed and safe)
    negative = bool(blocked_promoted or unsupported or not safe)
    notes = []
    if next_improved:
        notes.append('learning changed next action with evidence')
    if release_improved:
        notes.append('learning improved release sequence')
    if worker_improved:
        notes.append('learning changed worker preference safely')
    if failure_improved:
        notes.append('learning added failure warning')
    if negative:
        notes.append('negative or unsafe learning detected')
    return {
        'fixture_project': row.get('fixture_project', ''),
        'next_action_changed': next_changed,
        'next_action_improved': next_improved,
        'release_sequence_improved': release_improved,
        'worker_preference_improved': worker_improved,
        'failure_warning_added': failure_improved,
        'safety_boundary_preserved': safe,
        'negative_lift_detected': negative,
        'notes': '; '.join(notes) or 'neutral',
    }


def compare_baseline(
    project: Path, *, trace_path: Path | None = None, output_path: Path | None = None
) -> dict[str, Any]:
    trace = load_json(trace_path or dogfood_dir(project) / 'learning_dogfood_trace.json')
    rows = [compare_row(item) for item in trace.get('runs') or [] if isinstance(item, dict)]
    positive = sum(
        1
        for item in rows
        if any(
            item.get(key)
            for key in [
                'next_action_improved',
                'release_sequence_improved',
                'worker_preference_improved',
                'failure_warning_added',
            ]
        )
        and not item.get('negative_lift_detected')
    )
    negative = sum(1 for item in rows if item.get('negative_lift_detected'))
    payload = {
        'schema_version': '1.0',
        'generated_by': 'learning_baseline_comparator.py',
        'comparisons': rows,
        'summary': {
            'total_projects': len(rows),
            'projects_with_positive_lift': positive,
            'projects_with_negative_lift': negative,
            'neutral_projects': max(0, len(rows) - positive - negative),
        },
    }
    write_json(output_path or dogfood_dir(project) / 'baseline_comparison.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Compare learning disabled vs learning enabled dogfood results.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--trace', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = compare_baseline(
        project,
        trace_path=Path(args.trace).resolve() if args.trace else None,
        output_path=Path(args.output).resolve() if args.output else None,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
