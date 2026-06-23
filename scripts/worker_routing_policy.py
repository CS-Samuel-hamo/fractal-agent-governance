#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


TYPE_CAPABILITY = {
    'docs_update': 'docs_edit',
    'test_update': 'tests_edit',
    'code_edit': 'code_edit',
    'refactor': 'refactor',
    'repo_scan': 'repo_scan',
    'analysis': 'analysis',
    'release_readiness': 'repo_scan',
}


def risk_value(risk: str) -> int:
    return {'low': 1, 'medium': 2, 'high': 3}.get(str(risk or '').lower(), 2)


def worker_risk_limit_ok(worker: dict[str, Any], task_profile: dict[str, Any]) -> bool:
    return risk_value(str(task_profile.get('risk_level') or 'medium')) <= risk_value(str(worker.get('risk_limit') or 'low'))


def required_capability(task_profile: dict[str, Any]) -> str:
    return TYPE_CAPABILITY.get(str(task_profile.get('task_type') or ''), '')


def worker_can_route(worker: dict[str, Any], task_profile: dict[str, Any], *, mode: str) -> tuple[bool, str]:
    if not worker.get('available'):
        return False, 'worker_unavailable'
    if worker.get('health') == 'unavailable':
        return False, 'worker_unhealthy'
    if task_profile.get('trust_zone') == 'blocked':
        return False, 'blocked_zone'
    if mode == 'auto' and not worker.get('supports_actual_execution'):
        return False, 'actual_execution_not_supported'
    if mode in {'preview', 'needs_attention'} and not worker.get('supports_preview'):
        return False, 'preview_not_supported'
    if mode == 'auto' and not worker_risk_limit_ok(worker, task_profile):
        return False, 'risk_limit_exceeded'
    capability = required_capability(task_profile)
    if capability and capability not in (worker.get('capabilities') or []):
        return False, f'missing_capability:{capability}'
    return True, 'compatible'


def worker_score(worker: dict[str, Any], task_profile: dict[str, Any], *, mode: str) -> float:
    ok, _ = worker_can_route(worker, task_profile, mode=mode)
    if not ok:
        return -1000.0
    score = float(worker.get('reliability_score') or 0.0) * 10
    preferred_type = str(task_profile.get('preferred_worker_type') or '')
    worker_type = str(worker.get('worker_type') or '')
    provider = str(worker.get('provider') or '')
    task_type = str(task_profile.get('task_type') or '')
    if preferred_type and preferred_type == worker_type:
        score += 4.0
    if task_type == 'docs_update' and 'docs_edit' in (worker.get('capabilities') or []):
        score += 2.0
        if provider == 'codex':
            score += 12.0
        elif provider == 'openai_api':
            score += 4.0
        elif provider == 'local_docs':
            score += 2.0
    if task_type == 'test_update' and 'tests_edit' in (worker.get('capabilities') or []):
        score += 2.0
    if mode == 'preview' and provider == 'dry_run':
        score += 5.0
    if task_type in {'repo_scan', 'release_readiness'} and provider == 'local_scanner':
        score += 8.0
    if task_type == 'analysis' and provider == 'local_scanner':
        score += 2.0
    if mode == 'auto' and provider == 'mock':
        score += 1.0
    return score
