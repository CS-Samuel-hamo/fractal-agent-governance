from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path


HARD_RISK_TERMS = [
    'auth',
    'authorization',
    'authentication',
    'security',
    'secret',
    'credential',
    'token',
    'oauth',
    'jwt',
    'payment',
    'billing',
    'pii',
    'privacy',
    'migration',
    'production',
    'deployment',
    'release',
    'public api',
    'breaking change',
]

HARD_RISK_FILE_HINTS = [
    '.env',
    '.env.*',
    '**/*.pem',
    '**/*.key',
    'secrets/**',
    'credentials/**',
    '**/auth/**',
    '**/security/**',
    '**/payment/**',
    '**/billing/**',
    '**/migrations/**',
    'migrations/**',
    'database/**',
    'db/migrations/**',
    '**/deploy/**',
    '**/deployment/**',
    '**/production/**',
    '**/prod/**',
]

CROSS_SURFACE_HINTS = [
    'api',
    'service',
    'controller',
    'route',
    'schema',
    'dto',
    'model',
    'provider',
    'registry',
    'client',
    'worker',
    'queue',
]

DEFAULT_DENIED_FILES = ['.env', '.env.*', '**/*.pem', '**/*.key', 'secrets/**', 'credentials/**']


@dataclass(frozen=True)
class ExecutionPolicyInput:
    run_id: str
    task_id: str
    objective: str
    allowed_files: list[str]
    denied_files: list[str]
    test_commands: list[str]
    changed_file_estimate: int = 0
    force_path: str = ''
    governance_level: int | None = None


def safe_name(value: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in '._-' else '-' for ch in value).strip('-') or 'task'


def detect_hard_risk(objective: str, allowed_files: list[str]) -> list[dict]:
    hits = []
    objective_lower = objective.lower()
    for term in HARD_RISK_TERMS:
        if re.search(r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])', objective_lower):
            hits.append({'source': 'objective', 'match': term})

    for pattern in allowed_files:
        normalized = str(pattern).replace('\\', '/').lower()
        for hint in HARD_RISK_FILE_HINTS:
            hint_normalized = hint.lower()
            if fnmatch.fnmatch(normalized, hint_normalized) or hint_normalized.strip('*') in normalized:
                hits.append({'source': 'file_pattern', 'pattern': pattern, 'match': hint})
    return unique_dicts(hits)


def detect_cross_surface(allowed_files: list[str]) -> list[dict]:
    hits = []
    for pattern in allowed_files:
        parts = Path(str(pattern).replace('\\', '/')).parts
        normalized_parts = [p.lower().strip('*') for p in parts]
        normalized_text = '/'.join(normalized_parts)
        for hint in CROSS_SURFACE_HINTS:
            if hint in normalized_parts or f'/{hint}/' in f'/{normalized_text}/':
                hits.append({'source': 'file_pattern', 'pattern': pattern, 'match': hint})
    return unique_dicts(hits)


def unique_dicts(items: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def normalized_file_pattern(pattern: str) -> str:
    return str(pattern).replace('\\', '/').strip()


def is_test_pattern(pattern: str) -> bool:
    normalized = normalized_file_pattern(pattern).lower()
    parts = [p.strip('*').lower() for p in normalized.split('/') if p]
    return any(part in {'test', 'tests', 'spec', 'specs'} for part in parts) or 'test' in normalized or 'spec' in normalized


def conflict_key_for_pattern(pattern: str) -> str:
    normalized = normalized_file_pattern(pattern).strip('/')
    if not normalized or normalized in {'*', '**', '**/*'}:
        return 'repo:*'
    parts = [p for p in normalized.split('/') if p and '*' not in p]
    if not parts:
        return 'repo:*'
    if len(parts) == 1:
        return parts[0].lower()
    return '/'.join(parts[:2]).lower()


def conflict_keys_for_allowed_files(allowed_files: list[str]) -> list[str]:
    keys = []
    for pattern in allowed_files:
        if pattern:
            keys.append(conflict_key_for_pattern(pattern))
    return sorted(set(keys))


def chain_weight(path: str) -> str:
    if path == 'optimistic_worker':
        return 'light'
    if path == 'planned_worker':
        return 'medium'
    if path == 'fractal_governed':
        return 'heavy_parent_light_leaves'
    if path == 'human_gate':
        return 'blocked_until_approval'
    return 'unknown'


def verification_weight(verification_mode: str) -> str:
    if verification_mode == 'scope_guard_plus_tests':
        return 'medium'
    if verification_mode == 'scope_guard_only':
        return 'light_partial'
    return 'heavy_or_manual'


def rollback_mode(path: str) -> str:
    if path == 'optimistic_worker':
        return 'discard_isolated_worktree'
    if path == 'planned_worker':
        return 'task_pack_only_or_discard_isolated_worktree'
    if path == 'fractal_governed':
        return 'parent_artifact_only_then_discard_failed_leaf_worktrees'
    if path == 'human_gate':
        return 'no_execution_before_approval'
    return 'manual_review'


def judgment_nodes(
    policy_input: ExecutionPolicyInput,
    recommended_path: str,
    verification_mode: str,
    hard_risk_hits: list[dict],
    cross_surface_hits: list[dict],
) -> list[dict]:
    nodes = [
        {
            'id': 'task_context_envelope',
            'weight': 'light',
            'error_risk': 'low',
            'purpose': 'Attach durable project context without reclassifying the user request.',
        },
        {
            'id': 'hard_risk_gate',
            'weight': 'light',
            'error_risk': 'medium' if hard_risk_hits else 'low',
            'purpose': 'Detect auth, security, deployment, billing, privacy, migration, and secret risk.',
            'hit_count': len(hard_risk_hits),
        },
        {
            'id': 'scope_surface_gate',
            'weight': 'light',
            'error_risk': 'medium' if cross_surface_hits or len(policy_input.allowed_files) > 4 else 'low',
            'purpose': 'Estimate breadth from allowed file patterns and cross-surface hints.',
            'hit_count': len(cross_surface_hits),
        },
        {
            'id': 'verification_gate',
            'weight': verification_weight(verification_mode),
            'error_risk': 'low' if policy_input.test_commands else 'medium',
            'purpose': 'Choose scope guard only, scope guard plus tests, or manual/planned verification.',
            'test_command_count': len([x for x in policy_input.test_commands if x]),
        },
    ]
    if policy_input.governance_level is not None:
        nodes.insert(
            1,
            {
                'id': 'governance_level_hint',
                'weight': 'light',
                'error_risk': 'low',
                'purpose': 'Honor the parent governance level when supplied by Zoo.',
                'governance_level': policy_input.governance_level,
            },
        )
    if policy_input.force_path:
        nodes.insert(
            1,
            {
                'id': 'forced_path_override',
                'weight': 'light',
                'error_risk': 'medium',
                'purpose': 'Honor an explicit operator path override.',
                'forced_path': policy_input.force_path,
            },
        )
    if recommended_path == 'fractal_governed':
        nodes.append(
            {
                'id': 'leaf_decomposition_gate',
                'weight': 'medium',
                'error_risk': 'medium',
                'purpose': 'Convert the parent into leaf skeletons before execution.',
            }
        )
    if recommended_path == 'human_gate':
        nodes.append(
            {
                'id': 'human_approval_gate',
                'weight': 'heavy',
                'error_risk': 'low',
                'purpose': 'Stop before irreversible or policy-sensitive execution.',
            }
        )
    return nodes


def misroute_risk(
    policy_input: ExecutionPolicyInput,
    recommended_path: str,
    hard_risk_hits: list[dict],
    cross_surface_hits: list[dict],
    verification_mode: str,
) -> str:
    score = 0
    if policy_input.force_path:
        score += 2
    if hard_risk_hits:
        score += 1
    if len(cross_surface_hits) >= 2:
        score += 1
    if len(policy_input.allowed_files) > 4 or policy_input.changed_file_estimate > 4:
        score += 1
    if verification_mode == 'scope_guard_only':
        score += 1
    if recommended_path == 'optimistic_worker' and not policy_input.test_commands:
        score += 1
    if recommended_path in {'human_gate', 'fractal_governed'}:
        score = max(score - 1, 0)
    if score >= 4:
        return 'high'
    if score >= 2:
        return 'medium'
    return 'low'


def build_execution_graph(
    policy_input: ExecutionPolicyInput,
    recommended_path: str,
    reason: str,
    verification_mode: str,
    hard_risk_hits: list[dict],
    cross_surface_hits: list[dict],
) -> dict:
    conflict_keys = conflict_keys_for_allowed_files(policy_input.allowed_files)
    nodes = judgment_nodes(policy_input, recommended_path, verification_mode, hard_risk_hits, cross_surface_hits)
    parallelizable = recommended_path in {'optimistic_worker', 'planned_worker'}
    if recommended_path == 'planned_worker' and verification_mode == 'manual_or_planned_verification':
        parallelizable = False
    return {
        'schema_version': '1.0',
        'chain': recommended_path,
        'reason': reason,
        'chain_weight': chain_weight(recommended_path),
        'judgment_nodes': nodes,
        'judgment_node_count': len(nodes),
        'misroute_risk': misroute_risk(policy_input, recommended_path, hard_risk_hits, cross_surface_hits, verification_mode),
        'verification_weight': verification_weight(verification_mode),
        'parallel_contract': {
            'parallelizable': parallelizable,
            'conflict_keys': conflict_keys,
            'conflict_rule': 'do_not_run_in_parallel_with_tasks_that_share_any_conflict_key_unless_they_are_read_only',
            'parallel_group': f'{safe_name(policy_input.run_id)}/default',
        },
        'rollback_contract': {
            'mode': rollback_mode(recommended_path),
            'automatic_discard_supported': recommended_path in {'optimistic_worker', 'planned_worker'},
            'requires_human_before_execution': recommended_path == 'human_gate',
        },
        'chain_steps': [
            'task_context_envelope',
            'path_selection',
            recommended_path,
            verification_mode,
            rollback_mode(recommended_path),
        ],
    }


def select_execution_path(policy_input: ExecutionPolicyInput) -> dict:
    allowed_count = len([x for x in policy_input.allowed_files if x])
    test_count = len([x for x in policy_input.test_commands if x])
    hard_risk_hits = detect_hard_risk(policy_input.objective, policy_input.allowed_files)
    cross_surface_hits = detect_cross_surface(policy_input.allowed_files)
    changed_estimate = max(policy_input.changed_file_estimate, 0)

    if policy_input.force_path:
        recommended_path = policy_input.force_path
        reason = 'forced_by_user'
    elif policy_input.governance_level is not None and policy_input.governance_level >= 4:
        recommended_path = 'human_gate'
        reason = 'governance_level_4'
    elif policy_input.governance_level is not None and policy_input.governance_level == 3:
        recommended_path = 'fractal_governed'
        reason = 'governance_level_3'
    elif policy_input.governance_level is not None and policy_input.governance_level == 2:
        recommended_path = 'planned_worker'
        reason = 'governance_level_2'
    elif hard_risk_hits:
        recommended_path = 'planned_worker'
        reason = 'hard_risk_gate'
    elif changed_estimate > 10 or allowed_count > 8:
        recommended_path = 'fractal_governed'
        reason = 'large_or_broad_scope'
    elif changed_estimate > 4 or allowed_count > 4 or len(cross_surface_hits) >= 2:
        recommended_path = 'planned_worker'
        reason = 'multi_surface_or_medium_scope'
    else:
        recommended_path = 'optimistic_worker'
        reason = 'bounded_reversible_scope'

    if recommended_path == 'optimistic_worker' and test_count == 0:
        verification_mode = 'scope_guard_only'
    elif test_count:
        verification_mode = 'scope_guard_plus_tests'
    else:
        verification_mode = 'manual_or_planned_verification'

    execution_graph = build_execution_graph(
        policy_input,
        recommended_path,
        reason,
        verification_mode,
        hard_risk_hits,
        cross_surface_hits,
    )

    return {
        'run_id': policy_input.run_id,
        'task_id': policy_input.task_id,
        'recommended_path': recommended_path,
        'reason': reason,
        'hard_risk_hits': hard_risk_hits,
        'cross_surface_hits': cross_surface_hits,
        'allowed_file_count': allowed_count,
        'changed_file_estimate': changed_estimate,
        'test_command_count': test_count,
        'governance_level': policy_input.governance_level,
        'verification_mode': verification_mode,
        'requires_task_pack': recommended_path in {'planned_worker', 'fractal_governed'},
        'requires_human_gate': recommended_path == 'human_gate',
        'allow_optimistic_execution': recommended_path == 'optimistic_worker',
        'execution_graph': execution_graph,
    }
