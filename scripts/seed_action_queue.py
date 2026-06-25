#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from bounded_docs_writer import apply_docs_patch
from runtime_common import load_json, project_root, utc_now, write_json
from seed_prompt_discovery import discover_seed_prompt

QUEUE_SCHEMA_VERSION = '1.0'


def queue_path(project: Path) -> Path:
    return project / '.zoo-agent' / 'jobs' / 'seed_action_queue.json'


def _action(
    action_id: str, title: str, objective: str, target_files: list[str], *, source_file: str = ''
) -> dict[str, Any]:
    return {
        'action_id': action_id,
        'selected_action_id': action_id,
        'title': title,
        'objective': objective,
        'target_files': target_files,
        'risk_level': 'low',
        'execution_mode': 'auto',
        'trust_zone': 'trusted',
        'source': 'seed_prompt_queue',
        'source_file': source_file,
        'action_type': 'safe_docs_update',
        'status': 'pending',
        'changed_files': [],
        'completed_at': '',
        'reason': 'Next safe step derived from the seed prompt.',
        'expected_project_progress': 'Moves the project forward through safe documentation work.',
        'evidence': [
            {
                'kind': 'seed_prompt',
                'evidence_type': 'seed_prompt',
                'path': source_file or 'project_beginning_prompt.md',
                'trust_level': 'user_intent_evidence',
                'safety_checked': True,
            }
        ],
        'autopilot_eligible': True,
        'constraints': ['trusted_docs_only', 'no_script_execution', 'no_secret_access', 'no_overwrite'],
        'safety_constraints': [
            'trusted_docs_only',
            'no_script_execution',
            'no_secret_access',
            'no_external_network',
            'no_fake_citations',
            'no_fake_results',
        ],
    }


def default_actions(goal: str, *, source_file: str = '', research: bool = False) -> list[dict[str, Any]]:
    actions = [
        _action(
            'seed-starter-docs',
            'Create starter project documents from seed prompt',
            goal,
            ['README.md', 'docs/project_plan.md', *(['docs/research_workflow.md'] if research else [])],
            source_file=source_file,
        ),
        _action(
            'seed-literature-matrix',
            'Create literature matrix template',
            'Create a literature matrix template based on the seed prompt. Include columns for source, claim, method, evidence, limitation, and status. Do not invent citations.',
            ['docs/literature_matrix_template.md'],
            source_file=source_file,
        ),
        _action(
            'seed-evidence-plan',
            'Create evidence plan',
            'Create an evidence plan based on the seed prompt. Separate facts, assumptions, hypotheses, required evidence, and validation owner. Do not invent empirical results.',
            ['docs/evidence_plan.md'],
            source_file=source_file,
        ),
        _action(
            'seed-validation-checklist',
            'Create validation checklist',
            'Create a minimum viable validation checklist based on the seed prompt. Include smallest test, acceptance signal, failure signal, and next decision.',
            ['docs/validation_checklist.md'],
            source_file=source_file,
        ),
        _action(
            'seed-red-team-review',
            'Create red-team review template',
            'Create a red-team review template. Check for fake citations, fake data, overclaiming, missing uncertainty, and unsupported conclusions.',
            ['docs/red_team_review_template.md'],
            source_file=source_file,
        ),
    ]
    if not research:
        return [actions[0], actions[2], actions[3], actions[4]]
    return actions


def load_queue(project: Path) -> dict[str, Any]:
    return load_json(queue_path(project))


def save_queue(project: Path, queue: dict[str, Any]) -> dict[str, Any]:
    queue.update(
        {'schema_version': QUEUE_SCHEMA_VERSION, 'generated_by': 'seed_action_queue.py', 'updated_at': utc_now()}
    )
    write_json(queue_path(project), queue)
    return queue


def init_queue(project: Path, *, goal: str, source_file: str = '', research: bool = False) -> dict[str, Any]:
    queue = {
        'schema_version': QUEUE_SCHEMA_VERSION,
        'generated_by': 'seed_action_queue.py',
        'created_at': utc_now(),
        'updated_at': utc_now(),
        'goal': goal,
        'source_file': source_file or 'project_beginning_prompt.md',
        'status': 'active',
        'actions': default_actions(goal, source_file=source_file or 'project_beginning_prompt.md', research=research),
    }
    save_queue(project, queue)
    write_selected_action(project, next_pending_action_from_queue(queue) or {})
    return queue


def ensure_queue(project: Path, *, goal: str = '') -> dict[str, Any]:
    queue = load_queue(project)
    if queue.get('actions'):
        return queue
    seed_report = discover_seed_prompt(project, goal=goal)
    seed = seed_report.get('selected') if isinstance(seed_report.get('selected'), dict) else {}
    return init_queue(
        project,
        goal=goal or str(seed.get('summary') or 'Execute project seed prompt'),
        source_file=str(seed.get('path') or 'project_beginning_prompt.md'),
        research=bool(seed.get('research_seed')),
    )


def next_pending_action_from_queue(queue: dict[str, Any]) -> dict[str, Any]:
    for action in queue.get('actions') or []:
        if isinstance(action, dict) and action.get('status') == 'pending':
            return action
    return {}


def next_pending_action(project: Path) -> dict[str, Any]:
    return next_pending_action_from_queue(load_queue(project))


def progress_summary(project: Path) -> dict[str, Any]:
    queue = load_queue(project)
    actions = [item for item in queue.get('actions') or [] if isinstance(item, dict)]
    total = len(actions)
    completed_actions = [item for item in actions if item.get('status') == 'completed']
    pending_actions = [item for item in actions if item.get('status') == 'pending']
    completed = len(completed_actions)
    pending = len(pending_actions)
    next_action = pending_actions[0] if pending_actions else {}
    if not total:
        current_position = 'No project workflow plan has been generated yet.'
        phase_status = 'not_started'
    elif completed >= total:
        current_position = 'Phase 0 complete: reusable paper workflow scaffold is ready for review.'
        phase_status = 'complete'
    else:
        current_position = f'Phase 0 in progress: reusable paper workflow scaffold is {completed}/{total} complete.'
        phase_status = 'in_progress'
    return {
        'schema_version': QUEUE_SCHEMA_VERSION,
        'generated_by': 'seed_action_queue.py',
        'goal': queue.get('goal', ''),
        'source_file': queue.get('source_file', ''),
        'status': queue.get('status') or ('completed' if total and completed >= total else 'active'),
        'total_actions': total,
        'completed_actions': completed,
        'pending_actions': pending,
        'completed_titles': [str(item.get('title') or item.get('action_id') or '') for item in completed_actions],
        'next_action': {
            'title': next_action.get('title', ''),
            'target_files': next_action.get('target_files') or [],
        },
        'current_position': current_position,
        'overall_plan': [
            {
                'phase': 'Phase 0',
                'title': 'Reusable paper workflow scaffold',
                'status': phase_status,
            },
            {
                'phase': 'Phase 1',
                'title': 'Workflow hardening: prompts, templates, review checklist, and reusable operating guide',
                'status': 'next' if phase_status == 'complete' else 'later',
            },
            {
                'phase': 'Phase 2',
                'title': 'Apply the workflow to a concrete paper idea',
                'status': 'later',
            },
        ],
        'suggested_next_stage': (
            'Review the generated workflow package, then ask Agent to turn it into reusable templates and operating instructions.'
            if total and completed >= total
            else 'Run agent continue to complete the current workflow scaffold batch.'
        ),
    }


def mark_action(
    project: Path, action_id: str, *, status: str, changed_files: list[str] | None = None
) -> dict[str, Any]:
    queue = load_queue(project)
    for action in queue.get('actions') or []:
        if isinstance(action, dict) and action.get('action_id') == action_id:
            action.update(
                {
                    'status': status,
                    'changed_files': changed_files or [],
                    'completed_at': utc_now() if status in {'completed', 'skipped'} else '',
                }
            )
            break
    remaining = next_pending_action_from_queue(queue)
    queue['status'] = 'active' if remaining else 'completed'
    save_queue(project, queue)
    write_selected_action(project, remaining)
    return queue


def write_selected_action(project: Path, action: dict[str, Any]) -> None:
    if not action:
        payload = {
            'schema_version': QUEUE_SCHEMA_VERSION,
            'generated_by': 'seed_action_queue.py',
            'generated_at': utc_now(),
            'selected_action_id': '',
            'title': 'Seed prompt action queue completed',
            'reason': 'All safe seed prompt starter actions are complete.',
            'expected_project_progress': 'ready for the next user prompt',
            'risk_level': 'low',
            'target_files': [],
            'execution_mode': 'needs_attention',
            'trust_zone': 'trusted',
            'source': 'seed_prompt_queue',
        }
    else:
        payload = {
            **action,
            'schema_version': QUEUE_SCHEMA_VERSION,
            'generated_by': 'seed_action_queue.py',
            'generated_at': utc_now(),
        }
    write_json(project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json', payload)


def run_next(project: Path, *, goal: str = '') -> dict[str, Any]:
    queue = ensure_queue(project, goal=goal)
    action = next_pending_action_from_queue(queue)
    if not action:
        write_selected_action(project, {})
        return {
            'status': 'completed',
            'action': {},
            'changed_files': [],
            'remaining': 0,
            'summary': 'No queued seed prompt actions remain.',
        }
    result = apply_docs_patch(
        project,
        objective=str(action.get('objective') or action.get('title') or goal),
        target_files=[str(item) for item in action.get('target_files') or []],
    )
    changed = [str(item) for item in result.get('changed_files') or []]
    status = 'completed' if result.get('status') in {'success', 'skipped'} else 'blocked'
    queue = mark_action(project, str(action.get('action_id') or ''), status=status, changed_files=changed)
    remaining = len(
        [item for item in queue.get('actions') or [] if isinstance(item, dict) and item.get('status') == 'pending']
    )
    return {
        'status': 'working' if remaining else 'completed',
        'action': action,
        'actions': [action],
        'changed_files': changed,
        'remaining': remaining,
        'writer_status': result.get('status'),
        'blocked': result.get('blocked') or [],
        'summary': result.get('summary') or '',
        'stop_reason': 'queue_completed' if not remaining else 'step_completed',
    }


def run_batch(project: Path, *, goal: str = '', max_steps: int = 3) -> dict[str, Any]:
    actions_run: list[dict[str, Any]] = []
    changed_all: list[str] = []
    blocked: list[dict[str, Any]] = []
    steps = max(1, max_steps)
    for _ in range(steps):
        queue = ensure_queue(project, goal=goal)
        action = next_pending_action_from_queue(queue)
        if not action:
            write_selected_action(project, {})
            break
        result = apply_docs_patch(
            project,
            objective=str(action.get('objective') or action.get('title') or goal),
            target_files=[str(item) for item in action.get('target_files') or []],
        )
        changed = [str(item) for item in result.get('changed_files') or []]
        status = 'completed' if result.get('status') in {'success', 'skipped'} else 'blocked'
        actions_run.append({**action, 'writer_status': result.get('status'), 'changed_files': changed})
        changed_all.extend(changed)
        mark_action(project, str(action.get('action_id') or ''), status=status, changed_files=changed)
        if status == 'blocked':
            blocked.extend([item for item in result.get('blocked') or [] if isinstance(item, dict)])
            break
    queue = load_queue(project)
    remaining = len(
        [item for item in queue.get('actions') or [] if isinstance(item, dict) and item.get('status') == 'pending']
    )
    if blocked:
        stop_reason = 'needs_attention'
    elif remaining:
        stop_reason = 'reviewable_batch_complete'
    else:
        stop_reason = 'queue_completed'
    return {
        'status': 'needs_attention' if blocked else ('working' if remaining else 'completed'),
        'action': actions_run[-1] if actions_run else {},
        'actions': actions_run,
        'changed_files': changed_all,
        'remaining': remaining,
        'blocked': blocked,
        'summary': 'Completed a safe seed prompt batch.' if actions_run else 'No queued seed prompt actions remain.',
        'stop_reason': stop_reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Run the next safe seed prompt action.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--goal', default='')
    parser.add_argument('--init', action='store_true')
    parser.add_argument('--run-next', action='store_true')
    parser.add_argument('--run-batch', action='store_true')
    parser.add_argument('--max-steps', type=int, default=3)
    args = parser.parse_args()
    project = project_root(args.workspace)
    if args.init:
        payload = ensure_queue(project, goal=args.goal)
    elif args.run_batch:
        payload = run_batch(project, goal=args.goal, max_steps=args.max_steps)
    elif args.run_next:
        payload = run_next(project, goal=args.goal)
    else:
        payload = load_queue(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
