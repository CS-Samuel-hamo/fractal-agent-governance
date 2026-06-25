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

from execution_policy import (
    DEFAULT_DENIED_FILES,
    conflict_keys_for_allowed_files,
    detect_cross_surface,
    detect_hard_risk,
)
from runtime_common import project_root, utc_now, write_json

UNCERTAINTY_TERMS = [
    'maybe',
    'explore',
    'research',
    'investigate',
    'review',
    'refactor',
    'redesign',
    'optimize',
    'improve',
    'unknown',
    'unclear',
    'best',
    '\u5168\u9762',
    '\u91cd\u6784',
    '\u4f18\u5316',
    '\u5206\u6790',
    '\u8bc4\u4f30',
]

DEPENDENCY_TERMS = [
    'after',
    'before',
    'depends',
    'dependency',
    'then',
    'sequence',
    'blocked by',
    '\u5148',
    '\u7136\u540e',
    '\u518d',
    '\u4f9d\u8d56',
]

BLAST_RADIUS_TERMS = [
    'schema',
    'dto',
    'contract',
    'database',
    'db',
    'migration',
    'auth',
    'security',
    'api contract',
    'public api',
    'release',
    'deploy',
    'payment',
    'billing',
    '\u6743\u9650',
    '\u6570\u636e\u5e93',
    '\u8fc1\u79fb',
    '\u53d1\u5e03',
    '\u8ba4\u8bc1',
]

SEMANTIC_RESOURCE_PATTERNS = {
    'api_contract': ['api', 'endpoint', 'route', 'contract', 'openapi', 'swagger'],
    'dto_schema': ['dto', 'schema', 'model', 'serializer', 'validator'],
    'database_table': ['database', 'db', 'table', 'migration', 'sql', 'orm'],
    'fixture': ['fixture', 'seed', 'mock data', 'test data'],
}

PARALLEL_GOVERNANCE_TERMS = [
    'root',
    'parent',
    'governance',
    'review',
    'aggregation',
    'merge queue',
    'gpt review',
    'implementation queue',
]

BIG_TASK_TERMS = [
    'architecture',
    'system',
    'project',
    'multi-module',
    'cross-module',
    'end-to-end',
    'database schema',
    'public api',
    'api response',
    'migration',
    'refactor',
]

PATH_RE = re.compile(
    r'(?P<path>(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.@-]+\.(?:py|ts|tsx|js|jsx|json|md|yml|yaml|toml|css|scss|html|go|rs|java|cs))'
)


def term_hits(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def infer_patterns_from_text(text: str) -> list[str]:
    patterns = []
    for match in PATH_RE.finditer(text):
        patterns.append(match.group('path').replace('\\', '/'))
    if patterns:
        return sorted(set(patterns))
    lowered = text.lower()
    if 'readme' in lowered:
        patterns.append('README*')
    hints = [
        ('tests/**', ['test', 'tests', 'pytest', 'spec']),
        ('src/**', ['src', 'source', 'implementation']),
        ('docs/**', ['doc', 'docs', 'documentation']),
        ('scripts/**', ['script', 'scripts', 'cli']),
        ('frontend/**', ['frontend', 'react', 'next']),
        ('api/**', ['api', 'route']),
    ]
    for pattern, words in hints:
        if any(word in lowered for word in words):
            patterns.append(pattern)
    return sorted(set(patterns))


def semantic_resource_hits(text: str, allowed_files: list[str]) -> dict[str, list[str]]:
    surface = ' '.join([text, *allowed_files]).lower()
    hits: dict[str, list[str]] = {}
    for resource, terms in SEMANTIC_RESOURCE_PATTERNS.items():
        found = [term for term in terms if term in surface]
        if found:
            hits[resource] = found
    return hits


def has_explicit_file_patterns(allowed_files: list[str]) -> bool:
    return bool(allowed_files) and all('*' not in item for item in allowed_files)


def task_parallel_blockers(
    task_rows: list[dict[str, Any]], text: str, *, overlap: bool, hard_risk_hits: list[str], dependency_hits: list[str]
) -> list[str]:
    blockers: list[str] = []
    if len(task_rows) <= 1:
        blockers.append('single_task_no_parallelism')
    if overlap:
        blockers.append('shared_files_or_conflict_keys')
    if hard_risk_hits:
        blockers.append('hard_risk_hits')
    if dependency_hits:
        blockers.append('dependency_chain_detected')
    lowered = text.lower()
    governance_hits = [term for term in PARALLEL_GOVERNANCE_TERMS if term in lowered]
    if governance_hits:
        blockers.append('root_parent_governance_review_or_aggregation_node')

    for row in task_rows:
        allowed = [str(item) for item in row.get('allowed_files') or []]
        resources = semantic_resource_hits(str(row.get('objective') or ''), allowed)
        row['semantic_resource_hits'] = resources
        row['parallel_contract'] = {
            'separate_worktree': True,
            'separate_output_file': True,
            'separate_task_pack': True,
        }
        if resources:
            blockers.append('shared_semantic_resource_unknown')
        if not has_explicit_file_patterns(allowed):
            blockers.append('unknown_file_scope')

    return sorted(set(blockers))


def infer_project_patterns(project: Path) -> list[str]:
    candidates = [
        'src/**',
        'tests/**',
        'app/**',
        'lib/**',
        'packages/**',
        'services/**',
        'scripts/**',
        'frontend/src/**',
        'frontend/tests/**',
    ]
    found = [pattern for pattern in candidates if (project / pattern.split('/')[0]).exists()]
    return found or ['**']


def effective_allowed_files(project: Path, text: str, allowed_files: list[str]) -> list[str]:
    if allowed_files:
        return sorted(set(allowed_files))
    inferred = infer_patterns_from_text(text)
    if inferred:
        return inferred
    return infer_project_patterns(project)


def split_candidate_tasks(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    tasks = []
    for line in lines:
        cleaned = re.sub(r'^[-*]\s+', '', line)
        cleaned = re.sub(r'^\d+[\.)]\s+', '', cleaned)
        if cleaned and cleaned != text.strip():
            tasks.append(cleaned)
    if len(tasks) > 1:
        return tasks
    split_pattern = r'\s*(?:;|\band\b|,|' + chr(0xFF0C) + '|' + chr(0xFF1B) + r')\s*'
    chunks = [chunk.strip() for chunk in re.split(split_pattern, text) if chunk.strip()]
    return chunks if len(chunks) > 1 else [text.strip()]


def score_level(value: int) -> str:
    if value <= 0:
        return 'low'
    if value == 1:
        return 'medium'
    return 'high'


def detect_big_task(
    text: str,
    allowed_files: list[str],
    changed_file_estimate: int,
    hard_risk_hits: list[str],
    cross_surface_hits: list[str],
) -> tuple[bool, list[str]]:
    lowered = text.lower()
    reasons: list[str] = []
    for term in BIG_TASK_TERMS:
        if term in lowered:
            reasons.append(f'big_term:{term}')
    if len(allowed_files) > 4 or changed_file_estimate > 8:
        reasons.append('large_file_surface')
    if hard_risk_hits:
        reasons.append('hard_risk_surface')
    if len(cross_surface_hits) >= 2:
        reasons.append('cross_surface_change')
    return bool(reasons), reasons


def is_bounded_doc_edit(text: str, allowed_files: list[str]) -> bool:
    if not allowed_files or len(allowed_files) > 3:
        return False
    normalized = [str(item).replace('\\', '/') for item in allowed_files]
    if any('*' in item for item in normalized):
        return False
    if not all(
        item == 'README.md' or item.startswith('docs/') or item.lower().endswith(('.md', '.txt')) for item in normalized
    ):
        return False
    lowered = text.lower()
    action_terms = [
        'revise',
        'expand',
        'extend',
        'update',
        'edit',
        'improve',
        'add',
        '??',
        '??',
        '??',
        '??',
        '??',
        '??',
        '??',
    ]
    action_terms.extend(
        [
            '\u5b8c\u5584',
            '\u6269\u5c55',
            '\u7ec6\u5316',
            '\u4fee\u6539',
            '\u66f4\u65b0',
            '\u52a0\u5165',
            '\u8865\u5145',
        ]
    )
    return any(term in lowered for term in action_terms)


def classify(
    project: Path,
    text: str,
    *,
    allowed_files: list[str] | None = None,
    denied_files: list[str] | None = None,
    changed_file_estimate: int = 0,
    force_path: str = '',
) -> dict[str, Any]:
    allowed = effective_allowed_files(project, text, allowed_files or [])
    denied = denied_files or DEFAULT_DENIED_FILES
    hard_risk_hits = detect_hard_risk(text, allowed)
    cross_surface_hits = detect_cross_surface(allowed)
    uncertainty_hits = term_hits(text, UNCERTAINTY_TERMS)
    dependency_hits = term_hits(text, DEPENDENCY_TERMS)
    blast_hits = term_hits(text, BLAST_RADIUS_TERMS)
    semantic_hits = semantic_resource_hits(text, allowed)
    broad_allowed = allowed == ['**'] or len(allowed) > 4
    bounded_doc_edit = is_bounded_doc_edit(text, allowed)
    big_task, big_task_reasons = detect_big_task(
        text, allowed, changed_file_estimate, hard_risk_hits, cross_surface_hits
    )
    if bounded_doc_edit and not hard_risk_hits and not cross_surface_hits:
        big_task = False
        big_task_reasons = []

    coupling_score = 0
    if len(cross_surface_hits) >= 2:
        coupling_score += 1
    if broad_allowed:
        coupling_score += 1
    if len(allowed) > 8:
        coupling_score += 1

    uncertainty_score = 1 if uncertainty_hits else 0
    if allowed == ['**']:
        uncertainty_score += 1
    if 'review' in uncertainty_hits or '\u5168\u9762' in uncertainty_hits:
        uncertainty_score += 1

    blast_score = 0
    if hard_risk_hits or blast_hits:
        blast_score += 2
    if changed_file_estimate > 8:
        blast_score += 1

    dependency_score = 1 if dependency_hits else 0

    raw_tasks = split_candidate_tasks(text)
    task_rows = []
    seen_keys: set[str] = set()
    overlap = False
    for index, objective in enumerate(raw_tasks, start=1):
        task_allowed = effective_allowed_files(project, objective, [])
        keys = conflict_keys_for_allowed_files(task_allowed)
        if seen_keys.intersection(keys):
            overlap = True
        seen_keys.update(keys)
        task_rows.append(
            {
                'task_id': f'task-{index:03d}',
                'objective': objective,
                'allowed_files': task_allowed,
                'conflict_keys': keys,
                'independent': True,
            }
        )

    parallel_blockers = task_parallel_blockers(
        task_rows,
        text,
        overlap=overlap or any('repo:*' in row['conflict_keys'] for row in task_rows),
        hard_risk_hits=hard_risk_hits,
        dependency_hits=dependency_hits,
    )
    independent = len(parallel_blockers) == 0
    if not independent:
        for row in task_rows:
            row['independent'] = False
            row['parallel_denial_reason'] = parallel_blockers

    if force_path:
        path = force_path
        reason = 'forced_by_cli'
    elif independent:
        path = 'parallel'
        reason = 'independent_non_overlapping_tasks'
    elif big_task or blast_score >= 2 or coupling_score >= 2 or uncertainty_score >= 2 or dependency_score >= 1:
        path = 'governed'
        reason = 'big_task_readiness_required' if big_task else 'risk_or_coupling_requires_governance'
    else:
        path = 'fast'
        reason = 'low_coupling_low_uncertainty_low_blast_radius'

    return {
        'schema_version': '1.0',
        'generated_by': 'task_classifier.py',
        'generated_at': utc_now(),
        'input': text,
        'path': path,
        'reason': reason,
        'task_scale': 'big' if big_task else 'small',
        'big_task_reasons': big_task_reasons,
        'big_task_policy': {
            'root_codex_actual_allowed': False,
            'required_entrypoints': [
                'agent plan-big',
                'agent decompose',
                'python scripts/check_leaf_convergence.py',
                'agent aggregate',
                'python scripts/goal_completion_detector.py',
                'agent goal-loop',
                'agent global-loop',
                'agent integration-check',
            ]
            if big_task
            else [],
            'default_execution_mode': 'decomposition_only' if big_task else 'route_default',
            'leaf_resolution_policy': 'execute|refine_once|merge|defer|collapse',
            'goal_driven_loop': '/goal-set -> global loop -> scheduler -> active goal -> decomposition -> leaf execution -> aggregation -> goal update',
            'multi_goal_policy': 'one_active_goal_by_default_with_conflict_detection_and_starvation_prevention',
            'codex_role': 'leaf_execution_backend_only',
        },
        'independent': independent,
        'scores': {
            'coupling': score_level(coupling_score),
            'uncertainty': score_level(uncertainty_score),
            'blast_radius': score_level(blast_score),
            'dependency': score_level(dependency_score),
        },
        'score_values': {
            'coupling': coupling_score,
            'uncertainty': uncertainty_score,
            'blast_radius': blast_score,
            'dependency': dependency_score,
        },
        'signals': {
            'hard_risk_hits': hard_risk_hits,
            'cross_surface_hits': cross_surface_hits,
            'uncertainty_hits': uncertainty_hits,
            'dependency_hits': dependency_hits,
            'blast_radius_hits': blast_hits,
            'semantic_resource_hits': semantic_hits,
            'broad_allowed_files': broad_allowed,
            'bounded_doc_edit': bounded_doc_edit,
            'changed_file_estimate': changed_file_estimate,
        },
        'parallel_denial_reason': '' if independent else ';'.join(parallel_blockers),
        'independence_policy': {
            'unknown_is_independent': False,
            'required': [
                'no_shared_files',
                'no_shared_semantic_resources',
                'no_shared_api_contract',
                'no_shared_dto_schema',
                'no_shared_database_table',
                'no_shared_fixture',
                'no_dependency_chain',
                'separate_worktree',
                'separate_output_file',
                'separate_task_pack',
            ],
            'denied_nodes': ['root', 'parent', 'governance', 'review', 'aggregation'],
        },
        'allowed_files': allowed,
        'denied_files': denied,
        'tasks': task_rows,
        'path_contract': {
            'fast': 'Codex direct via fast backend, scope guard, tests, result; no planning or task splitting.',
            'parallel': 'Only independent tasks with disjoint conflict keys and separate worktrees/output paths.',
            'governed': 'Goal, decomposition, implementation queue, workers, reconciliation, aggregation, merge queue, GPT review.',
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify a CLI runtime task into fast, parallel, or governed path.')
    parser.add_argument('input', nargs='*')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--input-text', default='')
    parser.add_argument('--allowed-file', action='append', default=[])
    parser.add_argument('--denied-file', action='append', default=DEFAULT_DENIED_FILES)
    parser.add_argument('--changed-file-estimate', type=int, default=0)
    parser.add_argument('--force-path', choices=['', 'fast', 'parallel', 'governed'], default='')
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()

    text = args.input_text or ' '.join(args.input).strip()
    if not text:
        print('Missing task input.', file=sys.stderr)
        return 2
    project = project_root(args.workspace)
    report = classify(
        project,
        text,
        allowed_files=args.allowed_file,
        denied_files=args.denied_file,
        changed_file_estimate=args.changed_file_estimate,
        force_path=args.force_path,
    )
    if args.json_output:
        write_json(Path(args.json_output).resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
