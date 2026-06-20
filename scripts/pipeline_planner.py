#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from classify_goal_domain import classify_goal  # noqa: E402
from runtime_common import load_json, project_root, resolve_goal, safe_name, utc_now, write_json  # noqa: E402
from task_classifier import classify  # noqa: E402


def extract_resources(classification: dict[str, Any], allowed_files: list[str]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in allowed_files or classification.get('allowed_files') or []:
        normalized = str(path).replace('\\', '/')
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        resource_type = 'documentation_surface' if normalized.lower().endswith('.md') or normalized.startswith('docs/') else 'file_path'
        resources.append(
            {
                'resource_id': normalized,
                'type': resource_type,
                'paths': [normalized],
                'confidence': 'medium',
                'risk_level': 'low',
            }
        )
    for task in classification.get('tasks') or []:
        for key in task.get('conflict_keys') or []:
            normalized = str(key)
            if normalized and normalized not in seen:
                seen.add(normalized)
                resources.append(
                    {
                        'resource_id': normalized,
                        'type': 'unknown' if normalized.endswith('*') else 'file_path',
                        'paths': [],
                        'confidence': 'low',
                        'risk_level': 'unknown',
                    }
                )
    return resources


def build_leaf_tasks(classification: dict[str, Any], objective: str, denied_files: list[str]) -> list[dict[str, Any]]:
    source_tasks = classification.get('tasks') or []
    if not source_tasks:
        source_tasks = [{'task_id': 'task-001', 'objective': objective, 'allowed_files': classification.get('allowed_files') or []}]
    leaves: list[dict[str, Any]] = []
    for index, task in enumerate(source_tasks, start=1):
        allowed = [str(item) for item in task.get('allowed_files') or classification.get('allowed_files') or []]
        leaves.append(
            {
                'leaf_id': f'leaf-{index:03d}',
                'objective': str(task.get('objective') or objective),
                'task_type': 'docs' if any(str(item).lower().endswith('.md') or str(item).startswith('docs/') for item in allowed) else 'code',
                'risk_level': 'low' if not (classification.get('signals') or {}).get('hard_risk_hits') else 'high',
                'allowed_files': allowed,
                'denied_files': denied_files,
                'acceptance': [f'Complete: {task.get("objective") or objective}'],
                'preferred_route': classification.get('path') or 'fast',
                'execution_mode': 'dry_run_only',
                'resolution': 'execute' if allowed else 'defer',
            }
        )
    return leaves


def conflict_report_from_resources(resources: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [str(item.get('resource_id') or '') for item in resources if item.get('resource_id')]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    return {
        'conflicts': [
            {
                'type': 'resource',
                'severity': 'medium',
                'resource': item,
                'resolution': 'serial_execution',
            }
            for item in duplicates
        ],
        'conflict_count': len(duplicates),
        'policy': 'planner_internal_conflict_check_only',
    }


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    project = project_root(args.workspace)
    run_id = args.run_id or f'run-pipeline-{time.strftime("%Y%m%d%H%M%S", time.gmtime())}'
    objective = args.input_text or ' '.join(args.input).strip()
    if not objective:
        raise SystemExit('Missing pipeline task input.')
    goal = resolve_goal(project, args.goal_id) or {
        'goal_id': safe_name(args.goal_id or f'transient-{run_id}'),
        'goal': objective,
        'root_goal': objective,
        'success_criteria': [f'Verify outcome for: {objective}'],
        'priority': 50,
    }
    goal_domain = classify_goal(goal)
    classification = classify(project, objective, allowed_files=args.allowed_file, denied_files=args.denied_file, force_path=args.force_path)
    allowed_files = [str(item) for item in classification.get('allowed_files') or args.allowed_file]
    resources = extract_resources(classification, allowed_files)
    leaves = build_leaf_tasks(classification, objective, args.denied_file)
    actual_allowed = (
        goal_domain.get('goal_type') == 'production_goal'
        and not args.dry_run
        and classification.get('path') == 'fast'
        and classification.get('task_scale') != 'big'
    )
    execution_mode = 'actual_allowed' if actual_allowed else 'dry_run_only'
    for leaf in leaves:
        leaf['execution_mode'] = execution_mode if leaf['risk_level'] == 'low' else 'dry_run_only'
    return {
        'schema_version': '1.0',
        'generated_by': 'pipeline_planner.py',
        'generated_at': utc_now(),
        'stage': 'planner',
        'run_id': run_id,
        'workspace': str(project),
        'input': objective,
        'goal': {
            'goal_id': goal.get('goal_id'),
            'goal': goal.get('goal') or goal.get('root_goal') or objective,
            'priority': int(goal.get('priority') or 50),
            'goal_type': goal_domain.get('goal_type'),
            'success_criteria': goal.get('success_criteria') or [],
        },
        'classification': classification,
        'resource_graph': {
            'confidence': 'medium' if resources else 'low',
            'resources': resources,
        },
        'conflict_report': conflict_report_from_resources(resources),
        'decomposition': {
            'leaf_count': len(leaves),
            'leaf_tasks': leaves,
        },
        'execution_plan': {
            'route': classification.get('path') or 'fast',
            'mode': execution_mode,
            'executor_contract': 'executor_reads_plan_json_only',
            'verifier_contract': 'verifier_reads_execution_result_json_only',
        },
        'stage_boundaries': {
            'planner_writes': ['plan.json'],
            'executor_input': 'plan.json',
            'executor_output': 'execution_result.json',
            'verifier_input': 'execution_result.json',
            'verifier_output': 'final_result.json',
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Planner stage for the 3-stage Agent Runtime pipeline.')
    parser.add_argument('input', nargs='*')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--goal-id', default='')
    parser.add_argument('--input-text', default='')
    parser.add_argument('--allowed-file', action='append', default=[])
    parser.add_argument('--denied-file', action='append', default=['.env', '.env.*', '**/*.pem', '**/*.key', 'secrets/**', 'credentials/**'])
    parser.add_argument('--force-path', choices=['', 'fast', 'parallel', 'governed'], default='')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    plan = build_plan(args)
    project = project_root(args.workspace)
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'runs' / plan['run_id'] / 'pipeline' / 'plan.json'
    write_json(output, plan)
    print(json.dumps({'status': 'ok', 'plan_json': str(output), 'run_id': plan['run_id'], 'stage': 'planner'}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
