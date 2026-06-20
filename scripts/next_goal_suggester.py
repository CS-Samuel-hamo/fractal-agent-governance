#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, resolve_goal, utc_now, write_json  # noqa: E402


def run_dir(project: Path, run_id: str) -> Path:
    return project / '.zoo-agent' / 'runs' / run_id


def _candidate(candidate_id: str, title: str, rationale: str, *, priority: str = 'medium', execution_policy: str = 'suggestion_only') -> dict[str, Any]:
    return {
        'candidate_id': candidate_id,
        'title': title,
        'rationale': rationale,
        'priority': priority,
        'execution_policy': execution_policy,
        'auto_execute': False,
    }


def suggest_next_goals(project: Path, run_id: str, goal_id: str = '') -> dict[str, Any]:
    goal = resolve_goal(project, goal_id, run_id)
    completion = load_json(run_dir(project, run_id) / 'goal-completion.json')
    matrix = completion.get('goal_coverage_matrix') if isinstance(completion.get('goal_coverage_matrix'), dict) else load_json(run_dir(project, run_id) / 'goal-coverage-matrix.json')
    resource_map = load_json(project / '.zoo-agent' / 'project-resource-map.json')
    verdict = str(matrix.get('goal_completion_verdict') or '')
    missing = matrix.get('missing_success_criteria') or []
    failed = matrix.get('failed_leaf_ids') or []
    unreachable = matrix.get('unreachable_leaf_ids') or []
    candidates: list[dict[str, Any]] = []

    if verdict == 'COMPLETED':
        candidates.append(
            _candidate(
                'next-review-integration-candidate',
                'Review the integration candidate and choose the next bounded goal.',
                'The current goal is marked completed by parent aggregation; the next step should stay human-selected.',
                priority='high',
            )
        )
        if resource_map.get('unknowns'):
            candidates.append(
                _candidate(
                    'next-improve-resource-map',
                    'Improve the semantic resource map before broader work.',
                    'The completed run still has resource-map unknowns, which can limit safe parallelism.',
                )
            )
    elif verdict in {'PARTIAL', 'NEEDS_REPLAN'}:
        candidates.append(
            _candidate(
                'next-clarify-missing-success-criteria',
                'Clarify and decompose the missing success criteria.',
                f'{len(missing)} success criteria remain uncovered; do not expand unrelated leaf work.',
                priority='high',
            )
        )
    elif verdict == 'BLOCKED':
        candidates.append(
            _candidate(
                'next-resolve-blockers',
                'Resolve blocked leaf or backend issues before more execution.',
                f'Blocked or failed leaves: {", ".join(failed or unreachable) or "see aggregation report"}.',
                priority='high',
            )
        )
    elif verdict == 'DIVERGING':
        candidates.append(
            _candidate(
                'next-human-loop-decision',
                'Ask for a human/GPT decision on whether to replan, stop, or replace the goal.',
                'The loop is not converging; continuing automatic decomposition would waste execution budget.',
                priority='high',
            )
        )
    else:
        candidates.append(
            _candidate(
                'next-inspect-goal-state',
                'Inspect goal completion evidence before selecting a next goal.',
                'Goal completion verdict is unknown or incomplete.',
            )
        )

    report = {
        'schema_version': '1.0',
        'generated_by': 'next_goal_suggester.py',
        'generated_at': utc_now(),
        'run_id': run_id,
        'goal_id': goal.get('goal_id') or goal_id,
        'current_goal_status': verdict,
        'next_goal_candidates': candidates,
        'auto_execute': False,
        'auto_replace_goal': False,
    }
    return report


def write_next_goal_suggestions(project: Path, run_id: str, report: dict[str, Any]) -> dict[str, str]:
    path = run_dir(project, run_id) / 'next-goal-candidates.json'
    write_json(path, report)
    return {'next_goal_candidates': str(path)}


def suggest_and_write(project: Path, run_id: str, goal_id: str = '') -> dict[str, Any]:
    report = suggest_next_goals(project, run_id, goal_id)
    paths = write_next_goal_suggestions(project, run_id, report)
    report['paths'] = paths
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Suggest optional next goals after a goal loop iteration.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = suggest_and_write(project, args.run_id, args.goal_id)
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
