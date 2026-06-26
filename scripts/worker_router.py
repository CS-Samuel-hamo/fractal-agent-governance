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
from task_profile_classifier import classify_task_profile
from worker_capability_profile import worker_profiles
from worker_fallback_engine import fallback_trace, write_fallback_trace
from worker_registry import write_worker_registry
from worker_routing_policy import worker_can_route, worker_score


def workers_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'workers'


def _provider_or_name_match(worker: dict[str, Any], requested: str) -> bool:
    return requested in {str(worker.get('worker_name') or ''), str(worker.get('provider') or '')}


def _mode_from(task_profile: dict[str, Any], execution_mode: str = '') -> str:
    mode = str(execution_mode or '').lower()
    if mode in {'auto', 'preview', 'needs_attention'}:
        if mode == 'auto' and not task_profile.get('requires_actual_execution'):
            return 'preview'
        return mode
    if task_profile.get('trust_zone') == 'blocked':
        return 'needs_attention'
    return 'auto' if task_profile.get('requires_actual_execution') else 'preview'


def product_worker_type(worker_type: str) -> str:
    return {
        'code': 'Code Worker',
        'analysis': 'Analysis Worker',
        'test': 'Test Worker',
        'docs': 'Docs Worker',
        'mock': 'Test Worker',
        'dry_run': 'Dry-run Worker',
    }.get(worker_type, 'Worker')


def learning_worker_bonus(project: Path, worker: dict[str, Any], task_profile: dict[str, Any]) -> float:
    insights = (
        load_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'learning_insights.json').get('insights')
        or []
    )
    task_type = str(task_profile.get('task_type') or '').lower()
    preferred_type = str(task_profile.get('preferred_worker_type') or '').lower()
    worker_tokens = {
        str(worker.get('worker_name') or '').lower(),
        str(worker.get('provider') or '').lower(),
        str(worker.get('worker_type') or '').lower(),
        product_worker_type(str(worker.get('worker_type') or '')).lower(),
    }
    bonus = 0.0
    for item in insights:
        if not isinstance(item, dict):
            continue
        if item.get('type') != 'worker_preference' or item.get('recommended_effect') != 'prefer_worker':
            continue
        confidence = float(item.get('confidence') or 0.0)
        if confidence < 0.5:
            continue
        applies_to = str(item.get('applies_to') or '').lower()
        message = str(item.get('message') or '').lower()
        applies = applies_to in {task_type, preferred_type, 'worker_router'} or (applies_to and applies_to in task_type)
        mentions_worker = any(token and token in message for token in worker_tokens)
        if applies and mentions_worker:
            bonus += min(1.5, confidence)
    return bonus


def candidate_score(project: Path, worker: dict[str, Any], task_profile: dict[str, Any], *, mode: str) -> float:
    return worker_score(worker, task_profile, mode=mode) + learning_worker_bonus(project, worker, task_profile)


def route_worker(
    project: Path,
    *,
    task_profile: dict[str, Any],
    requested_worker: str = 'auto',
    execution_mode: str = '',
) -> dict[str, Any]:
    write_worker_registry(project)
    profiles = list(worker_profiles(project).values())
    requested = str(requested_worker or 'auto')
    mode = _mode_from(task_profile, execution_mode)
    if requested in {'dry_run', 'dry_run_worker'}:
        mode = 'preview'
    task_id = str(task_profile.get('task_id') or 'task')

    # Policy engine checks
    try:
        from policy_engine import check_cost_limit, check_security, evaluate_routing, load_policies

        policies = load_policies(project)
        task_type = str(task_profile.get('task_type', task_profile.get('intent', '')))
        risk_level = str(task_profile.get('risk_level', 'low'))
        files = [str(f) for f in task_profile.get('allowed_files', [])]

        # Security check
        sec = check_security(policies, action=str(task_profile.get('objective', '')), filepath=' '.join(files))
        if sec.get('decision') == 'deny':
            return {
                'schema_version': '1.0',
                'task_id': str(task_profile.get('task_id', 'task')),
                'selected_worker': '',
                'routing_reason': sec.get('reason', 'policy_blocked'),
                'execution_allowed': False,
                'execution_mode': 'blocked',
                'blocked_reason': sec['reason'],
            }

        # Cost limit check
        cost = check_cost_limit(policies, project)
        if not cost.get('within_limit'):
            return {
                'schema_version': '1.0',
                'task_id': str(task_profile.get('task_id', 'task')),
                'selected_worker': '',
                'routing_reason': cost.get('reason', 'cost_limit'),
                'execution_allowed': False,
                'execution_mode': 'blocked',
                'blocked_reason': cost['reason'],
            }

        # Routing policy
        policy_result = evaluate_routing(policies, task_type=task_type, risk_level=risk_level, file_patterns=files)
        if policy_result.get('block'):
            return {
                'schema_version': '1.0',
                'task_id': str(task_profile.get('task_id', 'task')),
                'selected_worker': '',
                'routing_reason': policy_result.get('message', 'policy_blocked'),
                'execution_allowed': False,
                'execution_mode': 'blocked',
                'blocked_reason': policy_result.get('message', 'Blocked by policy'),
            }
        if policy_result.get('require_worker'):
            requested = policy_result['require_worker']
        if policy_result.get('human_review'):
            mode = 'needs_attention'
    except ImportError:
        pass

    if task_profile.get('trust_zone') == 'blocked' or mode == 'needs_attention':
        decision = {
            'schema_version': '1.0',
            'generated_by': 'worker_router.py',
            'task_id': task_id,
            'task_profile': task_profile,
            'selected_worker': '',
            'selected_worker_type': '',
            'selected_provider': '',
            'worker_role': '',
            'routing_reason': 'blocked_zone_requires_attention'
            if task_profile.get('trust_zone') == 'blocked'
            else 'action_requires_attention',
            'fallback_workers': [],
            'execution_allowed': False,
            'execution_mode': 'needs_attention',
            'blocked_reason': 'blocked zone' if task_profile.get('trust_zone') == 'blocked' else 'attention required',
            'learning_feedback_ref': '.zoo-agent/learning/cross_project/learning_insights.json',
        }
        write_json(workers_dir(project) / 'routing_decision.json', decision)
        write_fallback_trace(
            project,
            fallback_trace(
                original_worker='',
                final_worker='',
                final_mode='needs_attention',
                reason=decision['blocked_reason'],
                safe=True,
            ),
        )
        return decision

    candidates = []
    rejected: list[dict[str, str]] = []
    for worker in profiles:
        ok, reason = worker_can_route(worker, task_profile, mode=mode)
        row = {
            'worker': str(worker.get('worker_name') or ''),
            'reason': reason,
            'detail': str(worker.get('unavailable_reason') or worker.get('reason') or ''),
        }
        if ok:
            candidates.append(worker)
        else:
            rejected.append(row)

    selected: dict[str, Any] | None = None
    route_reason = 'highest_compatible_capability_score'
    if requested and requested != 'auto':
        preferred = next((worker for worker in profiles if _provider_or_name_match(worker, requested)), None)
        if preferred:
            ok, reason = worker_can_route(preferred, task_profile, mode=mode)
            if ok:
                selected = preferred
                route_reason = f'requested_worker:{requested}'
            else:
                route_reason = f'requested_worker_fallback:{reason}'

    if selected is None and candidates:
        selected = sorted(
            candidates, key=lambda worker: candidate_score(project, worker, task_profile, mode=mode), reverse=True
        )[0]

    if selected is None:
        preview_candidates = []
        for worker in profiles:
            ok, _ = worker_can_route(worker, {**task_profile, 'requires_actual_execution': False}, mode='preview')
            if ok:
                preview_candidates.append(worker)
        selected = next((worker for worker in preview_candidates if worker.get('provider') == 'dry_run'), None)
        if selected:
            mode = 'preview'
            route_reason = 'downgraded_to_preview_no_actual_worker'
        else:
            decision = {
                'schema_version': '1.0',
                'generated_by': 'worker_router.py',
                'task_id': task_id,
                'task_profile': task_profile,
                'selected_worker': '',
                'selected_worker_type': '',
                'selected_provider': '',
                'worker_role': '',
                'routing_reason': 'no_safe_worker_available',
                'fallback_workers': [],
                'execution_allowed': False,
                'execution_mode': 'needs_attention',
                'blocked_reason': 'no safe worker available',
                'rejected_workers': rejected,
                'worker_unavailable_reasons': {
                    item['worker']: item.get('detail', item.get('reason', ''))
                    for item in rejected
                    if item.get('reason') in {'worker_unavailable', 'worker_unhealthy'}
                },
                'learning_feedback_ref': '.zoo-agent/learning/cross_project/learning_insights.json',
            }
            write_json(workers_dir(project) / 'routing_decision.json', decision)
            write_fallback_trace(
                project,
                fallback_trace(
                    original_worker=requested,
                    final_worker='',
                    final_mode='needs_attention',
                    reason='no_safe_worker_available',
                    safe=True,
                ),
            )
            return decision

    fallback_workers = [
        str(worker.get('worker_name') or '')
        for worker in sorted(
            candidates, key=lambda item: candidate_score(project, item, task_profile, mode=mode), reverse=True
        )
        if worker.get('worker_name') != selected.get('worker_name')
    ]
    if mode == 'auto' and 'dry_run_worker' not in fallback_workers:
        fallback_workers.append('dry_run_worker')
    decision = {
        'schema_version': '1.0',
        'generated_by': 'worker_router.py',
        'task_id': task_id,
        'task_profile': task_profile,
        'selected_worker': selected.get('worker_name', ''),
        'selected_worker_type': selected.get('worker_type', ''),
        'selected_provider': selected.get('provider', ''),
        'worker_role': product_worker_type(str(selected.get('worker_type') or '')),
        'routing_reason': route_reason,
        'fallback_workers': fallback_workers,
        'execution_allowed': bool(mode in {'auto', 'preview'}),
        'execution_mode': mode,
        'blocked_reason': '',
        'rejected_workers': rejected,
        'worker_unavailable_reasons': {
            item['worker']: item.get('detail', item.get('reason', ''))
            for item in rejected
            if item.get('reason') in {'worker_unavailable', 'worker_unhealthy'}
        },
        'registry_ref': '.zoo-agent/workers/worker_registry.json',
        'learning_feedback_ref': '.zoo-agent/learning/cross_project/learning_insights.json',
    }
    write_json(workers_dir(project) / 'routing_decision.json', decision)
    write_fallback_trace(
        project,
        fallback_trace(
            original_worker=requested if requested != 'auto' else str(selected.get('worker_name') or ''),
            fallback_chain=fallback_workers,
            final_worker=str(selected.get('worker_name') or ''),
            final_mode=mode,
            reason=route_reason,
            safe=True,
        ),
    )
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description='Route a task profile to a safe worker.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--task-profile', default='')
    parser.add_argument('--action', default='')
    parser.add_argument('--requested-worker', default='auto')
    parser.add_argument('--execution-mode', default='')
    parser.add_argument('--route-demo', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    if args.task_profile:
        task_profile = load_json(Path(args.task_profile).resolve())
    elif args.action:
        task_profile = classify_task_profile(load_json(Path(args.action).resolve()))
    elif args.route_demo:
        task_profile = {
            'task_id': 'demo-docs-action',
            'task_type': 'docs_update',
            'risk_level': 'low',
            'trust_zone': 'trusted',
            'requires_actual_execution': False,
            'requires_command_execution': False,
            'requires_long_context': False,
            'target_files': ['README.md'],
            'estimated_complexity': 'small',
            'preferred_worker_type': 'docs',
        }
    else:
        raise SystemExit('Provide --task-profile, --action, or --route-demo.')
    decision = route_worker(
        project, task_profile=task_profile, requested_worker=args.requested_worker, execution_mode=args.execution_mode
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision.get('execution_allowed') or decision.get('execution_mode') == 'needs_attention' else 1


if __name__ == '__main__':
    raise SystemExit(main())
