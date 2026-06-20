#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from execution_policy import detect_hard_risk, safe_name  # noqa: E402

SEMANTIC_RESOURCE_PATTERNS = {
    'api_contract': ['api', 'endpoint', 'route', 'contract', 'openapi', 'swagger'],
    'dto_schema': ['dto', 'schema', 'model', 'serializer', 'validator'],
    'database_table': ['database', 'db', 'table', 'migration', 'sql', 'orm'],
    'fixture': ['fixture', 'seed', 'mock data', 'test data'],
}

GOVERNANCE_NODE_TERMS = [
    'root',
    'parent',
    'governance',
    'review',
    'aggregation',
    'merge queue',
    'gpt review',
    'implementation queue',
]

DEPENDENCY_TERMS = ['after', 'before', 'depends', 'dependency', 'then', 'sequence', 'blocked by', '\u5148', '\u7136\u540e', '\u518d', '\u4f9d\u8d56']


def utc_now() -> str:
    import datetime

    return datetime.datetime.utcnow().isoformat() + 'Z'


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def git_root(workspace: Path) -> Path:
    import subprocess

    proc = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        cwd=workspace,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or 'workspace is not a git repository')
    return Path(proc.stdout.strip()).resolve()


def resolve_leaf_path(raw: str, index_path: Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = index_path.parent / path
    return path.resolve()


def load_leaves(leaf_index: Path) -> tuple[dict, list[dict]]:
    index = load_json(leaf_index)
    leaves = []
    for item in index.get('leaves') or []:
        if not isinstance(item, dict):
            continue
        leaf_path = resolve_leaf_path(str(item.get('json') or ''), leaf_index)
        leaf = load_json(leaf_path)
        if not leaf:
            leaf = dict(item)
        leaf['_leaf_path'] = str(leaf_path)
        leaves.append(leaf)
    return index, leaves


def leaf_conflict_keys(leaf: dict) -> list[str]:
    keys = leaf.get('conflict_keys')
    if isinstance(keys, list):
        return [str(item) for item in keys if str(item)]
    graph = leaf.get('execution_graph') if isinstance(leaf.get('execution_graph'), dict) else {}
    parallel = graph.get('parallel_contract') if isinstance(graph.get('parallel_contract'), dict) else {}
    keys = parallel.get('conflict_keys')
    if isinstance(keys, list):
        return [str(item) for item in keys if str(item)]
    return []


def wildcard_or_unknown(pattern: str) -> bool:
    return '*' in pattern or not pattern.strip()


def semantic_resource_hits(objective: str, allowed_files: list[str]) -> dict[str, list[str]]:
    surface = ' '.join([objective, *allowed_files]).lower()
    hits: dict[str, list[str]] = {}
    for resource, terms in SEMANTIC_RESOURCE_PATTERNS.items():
        found = [term for term in terms if term in surface]
        if found:
            hits[resource] = found
    return hits


def governance_node_hits(leaf: dict) -> list[str]:
    surface = ' '.join([str(leaf.get('task_id') or ''), str(leaf.get('objective') or '')]).lower()
    return [term for term in GOVERNANCE_NODE_TERMS if term in surface]


def dependency_hits(leaf: dict) -> list[str]:
    surface = str(leaf.get('objective') or '').lower()
    return [term for term in DEPENDENCY_TERMS if term in surface]


def expected_paths(repo_root: Path, run_id: str, parent_task_id: str, leaf: dict) -> dict:
    task_id = safe_name(str(leaf.get('task_id') or 'leaf'))
    worktree_root = repo_root / '.zoo-agent' / 'worktrees' / safe_name(run_id) / 'parallel' / safe_name(parent_task_id) / task_id
    return {
        'worktree_root': str(worktree_root),
        'task_pack_dir': str(worktree_root / 'attempt-1' / '.zoo-agent' / 'runs' / run_id / 'codex-tasks' / task_id),
        'collected_result': str(worktree_root / 'attempt-1' / '.zoo-agent' / 'runs' / run_id / 'codex-results' / task_id / 'result.json'),
        'dispatcher_report': str(repo_root / '.zoo-agent' / 'runs' / run_id / 'dispatcher-runs' / f'{task_id}.json'),
        'optimistic_report': str(repo_root / '.zoo-agent' / 'runs' / run_id / 'optimistic-runs' / f'{task_id}.json'),
        'worker_log_dir': str(repo_root / '.zoo-agent' / 'runs' / run_id / 'parallel-workers' / safe_name(parent_task_id) / task_id),
    }


def build_contract(repo_root: Path, run_id: str, leaf_index_path: Path, *, max_workers: int, allow_planned: bool = False) -> dict:
    index, leaves = load_leaves(leaf_index_path)
    parent_task_id = str(index.get('parent_task_id') or (leaves[0].get('parent_task_id') if leaves else 'parallel-workers'))
    blockers: list[dict] = []
    locks: dict[str, str] = {}
    schedule = []
    seen_task_ids: set[str] = set()
    seen_paths: dict[str, str] = {}
    seen_allowed: dict[str, str] = {}

    for leaf in leaves:
        task_id = str(leaf.get('task_id') or '')
        if not task_id:
            blockers.append({'id': 'missing_task_id', 'leaf': leaf.get('_leaf_path', '')})
            continue
        if task_id in seen_task_ids:
            blockers.append({'id': 'duplicate_task_id', 'task_id': task_id})
        seen_task_ids.add(task_id)

        if leaf.get('parallelizable') is not True:
            blockers.append({'id': 'leaf_not_parallelizable', 'task_id': task_id})

        path = str(leaf.get('recommended_execution_path') or '')
        if path != 'optimistic_worker' and not (allow_planned and path == 'planned_worker'):
            blockers.append({'id': 'unsupported_parallel_execution_path', 'task_id': task_id, 'path': path})

        allowed = [str(item) for item in (leaf.get('allowed_files') or []) if str(item)]
        if not allowed:
            blockers.append({'id': 'missing_allowed_files', 'task_id': task_id})
        for pattern in allowed:
            if wildcard_or_unknown(pattern):
                blockers.append({'id': 'unknown_file_scope_not_parallel_safe', 'task_id': task_id, 'pattern': pattern})
            owner = seen_allowed.get(pattern)
            if owner and owner != task_id:
                blockers.append({'id': 'shared_allowed_file_pattern', 'pattern': pattern, 'tasks': [owner, task_id]})
            seen_allowed[pattern] = task_id

        governance_hits = governance_node_hits(leaf)
        if governance_hits:
            blockers.append({'id': 'governance_node_not_parallel_worker', 'task_id': task_id, 'hits': governance_hits})
        chain_hits = dependency_hits(leaf)
        if chain_hits:
            blockers.append({'id': 'dependency_chain_detected', 'task_id': task_id, 'hits': chain_hits})

        semantic_hits = semantic_resource_hits(str(leaf.get('objective') or ''), allowed)
        if semantic_hits:
            blockers.append({'id': 'semantic_resource_unknown_not_parallel_safe', 'task_id': task_id, 'hits': semantic_hits})

        hard_risk_hits = detect_hard_risk(str(leaf.get('objective') or ''), allowed)
        if hard_risk_hits:
            blockers.append({'id': 'hard_risk_leaf_not_parallel_safe', 'task_id': task_id, 'hits': hard_risk_hits})

        keys = leaf_conflict_keys(leaf)
        if not keys:
            blockers.append({'id': 'missing_conflict_keys', 'task_id': task_id})
        for key in keys:
            if key == 'repo:*':
                blockers.append({'id': 'repo_wide_conflict_key', 'task_id': task_id, 'conflict_key': key})
            owner = locks.get(key)
            if owner and owner != task_id:
                blockers.append({'id': 'conflict_key_overlap', 'conflict_key': key, 'tasks': [owner, task_id]})
            locks[key] = task_id

        paths = expected_paths(repo_root, run_id, parent_task_id, leaf)
        for key, value in paths.items():
            owner = seen_paths.get(value)
            if owner and owner != task_id:
                blockers.append({'id': 'shared_output_or_worktree_path', 'path_kind': key, 'path': value, 'tasks': [owner, task_id]})
            seen_paths[value] = task_id

        schedule.append(
            {
                'task_id': task_id,
                'parent_task_id': parent_task_id,
                'leaf_path': leaf.get('_leaf_path', ''),
                'recommended_execution_path': path,
                'parallelizable': leaf.get('parallelizable'),
                'conflict_keys': keys,
                'allowed_files': allowed,
                'test_commands': leaf.get('test_commands') or [],
                'semantic_resource_hits': semantic_hits,
                'expected_paths': paths,
            }
        )

    parallel_denial_reason = ';'.join(sorted({str(item.get('id')) for item in blockers if item.get('id')}))

    return {
        'schema_version': '1.0',
        'generated_by': 'check_codex_worker_concurrency.py',
        'generated_at': utc_now(),
        'status': 'pass' if not blockers and leaves else 'blocked',
        'run_id': run_id,
        'parent_task_id': parent_task_id,
        'leaf_index': str(leaf_index_path),
        'leaf_count': len(leaves),
        'max_workers': max(1, max_workers),
        'allow_planned': allow_planned,
        'blockers': blockers,
        'parallel_denial_reason': parallel_denial_reason,
        'resource_locks': [{'conflict_key': key, 'task_id': task_id} for key, task_id in sorted(locks.items())],
        'branch_schedule': schedule,
        'rules': [
            'Unknown independence is treated as not independent.',
            'No shared files.',
            'No shared semantic resources.',
            'No shared API contract.',
            'No shared DTO/schema.',
            'No shared database table.',
            'No shared fixture.',
            'No dependency chain.',
            'Separate worktree per worker.',
            'Separate output file per worker.',
            'Separate task pack per worker.',
            'Root, parent, governance, review, and aggregation nodes cannot enter parallel workers.',
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='Validate whether Codex worker leaves are safe to run in parallel.')
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--leaf-index', required=True)
    ap.add_argument('--output-dir', default='')
    ap.add_argument('--max-workers', type=int, default=4)
    ap.add_argument('--allow-planned', action='store_true')
    ap.add_argument('--json-output', default='')
    args = ap.parse_args()

    repo_root = git_root(Path(args.workspace).resolve())
    leaf_index = Path(args.leaf_index).resolve()
    contract = build_contract(repo_root, args.run_id, leaf_index, max_workers=args.max_workers, allow_planned=args.allow_planned)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else repo_root / '.zoo-agent' / 'runs' / args.run_id / 'parallel-workers' / safe_name(contract['parent_task_id'])
    write_json(output_dir / 'resource-locks.json', {'resource_locks': contract['resource_locks'], 'status': contract['status'], 'blockers': contract['blockers']})
    write_json(output_dir / 'branch-schedule.json', {'branch_schedule': contract['branch_schedule'], 'status': contract['status'], 'max_workers': contract['max_workers']})
    write_json(output_dir / 'concurrency-check.json', contract)
    if args.json_output:
        write_json(Path(args.json_output).resolve(), contract)
    print(json.dumps(contract, ensure_ascii=False, indent=2))
    return 0 if contract['status'] == 'pass' else 20


if __name__ == '__main__':
    raise SystemExit(main())
