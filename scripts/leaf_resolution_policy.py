#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

LEAF_STATES = {
    'ready_for_codex_execution',
    'needs_refinement',
    'should_merge_to_parent',
    'should_defer',
    'should_collapse_to_micro_task',
    'blocked',
}

FINAL_ACTIONS = {'execute', 'merge', 'defer', 'collapse', 'blocked'}
DEFAULT_MAX_REFINEMENTS = 1


def _items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []


def refinement_count(leaf: dict[str, Any]) -> int:
    resolution = leaf.get('resolution') if isinstance(leaf.get('resolution'), dict) else {}
    for key in ['refinement_count', 'refine_count']:
        try:
            return int(resolution.get(key) if key in resolution else leaf.get(key) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def has_unknown_resource(leaf: dict[str, Any]) -> bool:
    resources = _items(leaf.get('owned_resources')) + _items(leaf.get('provides')) + _items(leaf.get('consumes'))
    return any(item.lower() in {'unknown', '*', 'tbd'} for item in resources)


def scope_is_clear(leaf: dict[str, Any]) -> bool:
    return bool(_items(leaf.get('allowed_files')) and _items(leaf.get('denied_files')))


def acceptance_is_clear(leaf: dict[str, Any]) -> bool:
    return bool(_items(leaf.get('acceptance')))


def is_micro_task_candidate(leaf: dict[str, Any]) -> bool:
    objective = str(leaf.get('objective') or '').lower()
    allowed_files = _items(leaf.get('allowed_files'))
    if leaf.get('micro_task') is True or leaf.get('collapse_hint') is True:
        return scope_is_clear(leaf) and acceptance_is_clear(leaf)
    small_terms = ['typo', 'wording', 'exact line', 'single file', 'small docs', 'micro', 'minimal']
    return (
        len(allowed_files) == 1
        and acceptance_is_clear(leaf)
        and any(term in objective for term in small_terms)
        and str(leaf.get('risk_level') or 'low') == 'low'
        and str(leaf.get('task_type') or '') not in {'research', 'review', 'integration'}
    )


def resolution_record(
    leaf: dict[str, Any],
    *,
    leaf_state: str,
    action: str,
    reason: str,
    readiness: dict[str, Any],
    max_refinements: int,
    resolution_path: list[str] | None = None,
) -> dict[str, Any]:
    count = refinement_count(leaf)
    final = action in FINAL_ACTIONS
    return {
        'schema_version': '1.0',
        'leaf_id': leaf.get('leaf_id'),
        'run_id': leaf.get('run_id'),
        'leaf_state': leaf_state,
        'resolution': action,
        'final': final,
        'reason': reason,
        'readiness_verdict': readiness.get('verdict'),
        'blocking_reasons': readiness.get('blocking_reasons') or [],
        'refinement_count': count,
        'max_refinements': max_refinements,
        'resolution_path': resolution_path or [],
        'next_action': next_action_for(action),
    }


def next_action_for(action: str) -> str:
    return {
        'execute': 'queue_codex_leaf_execution_after_explicit_confirmation',
        'refine': 'regenerate_leaf_contract_once_then_resolve_again',
        'merge': 'lift_obligation_to_parent_aggregation',
        'defer': 'write_follow_up_backlog_and_continue_parent_flow',
        'collapse': 'convert_to_bounded_codex_micro_task',
        'blocked': 'human_or_gpt_decision_required',
    }.get(action, 'inspect_leaf_resolution')


def leaf_resolution_policy(
    leaf: dict[str, Any],
    readiness: dict[str, Any],
    *,
    backend_profile: dict[str, Any] | None = None,
    max_refinements: int = DEFAULT_MAX_REFINEMENTS,
    independence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one leaf into execute/refine/merge/defer/collapse/blocked.

    This policy intentionally does not launch Codex. It decides whether a leaf is
    eligible for a later bounded Codex execution queue, or should converge into a
    non-execution state.
    """
    verdict = str(readiness.get('verdict') or '')
    blockers = {str(item) for item in readiness.get('blocking_reasons') or []}
    count = refinement_count(leaf)
    backend_status = str((backend_profile or {}).get('health_status') or 'unknown')
    independence_reason = str((independence or {}).get('reason') or '')

    if verdict == 'READY_FOR_ACTUAL_CODEX':
        if independence_reason and 'unknown' in independence_reason:
            return resolution_record(
                leaf,
                leaf_state='should_defer',
                action='defer',
                reason='independence_unknown',
                readiness=readiness,
                max_refinements=max_refinements,
            )
        return resolution_record(
            leaf,
            leaf_state='ready_for_codex_execution',
            action='execute',
            reason='leaf_ready_for_bounded_codex_execution',
            readiness=readiness,
            max_refinements=max_refinements,
        )

    if is_micro_task_candidate(leaf) and verdict in {'READY_FOR_DRY_RUN', 'BLOCKED_BACKEND_UNHEALTHY'}:
        return resolution_record(
            leaf,
            leaf_state='should_collapse_to_micro_task',
            action='collapse',
            reason='leaf_is_bounded_micro_task',
            readiness=readiness,
            max_refinements=max_refinements,
        )

    if blockers.intersection({'missing_acceptance', 'missing_scope'}):
        if count < max_refinements:
            return resolution_record(
                leaf,
                leaf_state='needs_refinement',
                action='refine',
                reason='missing_acceptance_or_scope',
                readiness=readiness,
                max_refinements=max_refinements,
            )
        if has_unknown_resource(leaf) or not scope_is_clear(leaf):
            return resolution_record(
                leaf,
                leaf_state='should_merge_to_parent',
                action='merge',
                reason='scope_or_resource_not_independent_after_refine',
                readiness=readiness,
                max_refinements=max_refinements,
            )
        return resolution_record(
            leaf,
            leaf_state='should_defer',
            action='defer',
            reason='acceptance_or_scope_still_incomplete_after_refine',
            readiness=readiness,
            max_refinements=max_refinements,
        )

    if 'unstable_consumes' in blockers or has_unknown_resource(leaf):
        return resolution_record(
            leaf,
            leaf_state='should_merge_to_parent',
            action='merge',
            reason='leaf_not_independent_from_parent_resources',
            readiness=readiness,
            max_refinements=max_refinements,
        )

    if 'high_risk_leaf' in blockers or str(leaf.get('risk_level') or '') in {'high', 'critical'}:
        return resolution_record(
            leaf,
            leaf_state='should_defer',
            action='defer',
            reason='high_risk_leaf_requires_human_gate',
            readiness=readiness,
            max_refinements=max_refinements,
        )

    if verdict in {'BLOCKED_BACKEND_UNHEALTHY', 'BLOCKED_TEST_POLICY_UNKNOWN', 'READY_FOR_MANUAL_REVIEW'}:
        reason = (
            'backend_not_ready'
            if backend_status not in {'healthy', 'healthy_with_warnings'}
            else 'manual_or_test_policy_required'
        )
        return resolution_record(
            leaf,
            leaf_state='should_defer',
            action='defer',
            reason=reason,
            readiness=readiness,
            max_refinements=max_refinements,
        )

    if verdict == 'READY_FOR_DRY_RUN':
        return resolution_record(
            leaf,
            leaf_state='should_defer',
            action='defer',
            reason='dry_run_leaf_waits_for_explicit_actual_permission',
            readiness=readiness,
            max_refinements=max_refinements,
        )

    return resolution_record(
        leaf,
        leaf_state='blocked',
        action='blocked',
        reason='convergence_failure_no_resolution_path',
        readiness=readiness,
        max_refinements=max_refinements,
    )
