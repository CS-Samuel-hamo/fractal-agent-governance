#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, safe_name, utc_now, write_json


def git_root(workspace: Path) -> Path:
    proc = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        cwd=workspace,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or 'workspace is not a git repository')
    return Path(proc.stdout.strip()).resolve()


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    return {
        'command': [str(item) for item in command],
        'cwd': str(cwd),
        'returncode': proc.returncode,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def git_branch(workspace: Path) -> str:
    result = run_command(['git', 'branch', '--show-current'], workspace)
    return str(result.get('stdout') or '').strip()


def git_toplevel(workspace: Path) -> str:
    result = run_command(['git', 'rev-parse', '--show-toplevel'], workspace)
    return str(result.get('stdout') or '').strip()


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def collect_strings(value: Any, key_name: str) -> list[str]:
    rows: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == key_name and isinstance(item, str):
                rows.append(item)
            rows.extend(collect_strings(item, key_name))
    elif isinstance(value, list):
        for item in value:
            rows.extend(collect_strings(item, key_name))
    return rows


def json_mentions_task(payload: Any, task_id: str) -> bool:
    if isinstance(payload, dict):
        if str(payload.get('task_id') or '') == task_id:
            return True
        return any(json_mentions_task(item, task_id) for item in payload.values())
    if isinstance(payload, list):
        return any(json_mentions_task(item, task_id) for item in payload)
    if isinstance(payload, str):
        return task_id in payload
    return False


def discover_worktrees(repo_root: Path, run_id: str, task_id: str) -> list[Path]:
    managed_root = repo_root / '.zoo-agent' / 'worktrees'
    candidates: set[Path] = set()
    run_dir = repo_root / '.zoo-agent' / 'runs' / run_id
    if run_dir.exists():
        for json_path in run_dir.rglob('*.json'):
            payload = load_json(json_path)
            if not payload or not json_mentions_task(payload, task_id):
                continue
            for value in collect_strings(payload, 'worktree'):
                if value:
                    candidates.add(Path(value).resolve())
            for value in collect_strings(payload, 'worktree_path'):
                if value:
                    candidates.add(Path(value).resolve())

    default_roots = [
        managed_root / safe_name(run_id) / safe_name(task_id),
        managed_root / safe_name(run_id) / 'parallel',
    ]
    for root in default_roots:
        if not root.exists():
            continue
        for path in root.rglob('*'):
            if path.is_dir() and safe_name(task_id) in path.name:
                if (path / '.git').exists():
                    candidates.add(path.resolve())
                else:
                    for child in path.iterdir():
                        if child.is_dir():
                            candidates.add(child.resolve())
        if root.name == safe_name(task_id):
            for path in root.iterdir():
                if path.is_dir():
                    candidates.add(path.resolve())

    filtered = []
    for path in sorted(candidates, key=lambda item: str(item)):
        if is_relative_to(path, managed_root) and ((path / '.git').exists() or not path.exists()):
            filtered.append(path)
    return filtered


def is_isolated_worktree(path: Path, repo_root: Path, managed_root: Path) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not path.exists():
        return True, reasons
    if not is_relative_to(path, managed_root):
        reasons.append('outside_managed_worktree_root')
    if path.resolve() == repo_root.resolve():
        reasons.append('target_is_repo_root')
    if not (path / '.git').exists():
        reasons.append('missing_git_worktree_marker')
    top = git_toplevel(path)
    if top and Path(top).resolve() != path.resolve():
        reasons.append('target_not_git_toplevel')
    return not reasons, reasons


def write_patch_plan(path: Path, rollback_dir: Path, task_id: str, index: int) -> str:
    patch_path = rollback_dir / f'{safe_name(task_id)}-{index:03d}.patch'
    if not path.exists():
        write_json(patch_path.with_suffix('.patch.json'), {'status': 'target_missing', 'path': str(path)})
        return str(patch_path)
    result = run_command(['git', 'diff', '--binary'], path)
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(str(result.get('stdout') or ''), encoding='utf-8')
    return str(patch_path)


def release_locks(repo_root: Path, run_id: str, task_id: str, *, dry_run: bool) -> dict[str, Any]:
    lock_path = repo_root / '.zoo-agent' / 'locks' / 'resource-locks.json'
    payload = load_json(lock_path)
    locks = payload.get('locks') if isinstance(payload.get('locks'), list) else []
    kept = []
    released = []
    safe_task = safe_name(task_id)
    for lock in locks:
        if not isinstance(lock, dict):
            kept.append(lock)
            continue
        owner = str(lock.get('owner') or '')
        lock_run = str(lock.get('run_id') or '')
        if lock_run == run_id and (safe_task in owner or task_id in owner or not owner):
            released.append(lock)
        else:
            kept.append(lock)
    if released and not dry_run:
        payload['locks'] = kept
        payload['updated_at'] = utc_now()
        write_json(lock_path, payload)
    return {'lock_path': str(lock_path), 'released': released, 'dry_run': dry_run}


def rollback(args) -> tuple[int, dict[str, Any]]:
    if not args.yes:
        args.dry_run = True
    repo_root = git_root(Path(args.workspace).resolve())
    managed_root = repo_root / '.zoo-agent' / 'worktrees'
    rollback_dir = repo_root / '.zoo-agent' / 'runs' / args.run_id / 'rollback'
    targets = discover_worktrees(repo_root, args.run_id, args.task_id)
    blockers: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    current_branch = git_branch(repo_root)

    for index, path in enumerate(targets, start=1):
        if not is_relative_to(path, managed_root):
            blockers.append({'id': 'worktree_outside_managed_root', 'path': str(path)})
            continue
        isolated, isolation_reasons = is_isolated_worktree(path, repo_root, managed_root)
        if not isolated:
            blockers.append({'id': 'target_not_isolated_worktree', 'path': str(path), 'reasons': isolation_reasons})
        target_branch = git_branch(path) if path.exists() else ''
        if (
            path.exists()
            and target_branch
            and target_branch in {current_branch, 'main', 'master'}
            and not args.confirm_current_branch
        ):
            blockers.append(
                {
                    'id': 'protected_branch_requires_second_confirmation',
                    'path': str(path),
                    'branch': target_branch,
                    'required_flag': '--confirm-current-branch',
                }
            )
        action: dict[str, Any] = {
            'path': str(path),
            'exists': path.exists(),
            'managed_root': str(managed_root),
            'dry_run': args.dry_run,
            'isolated_worktree': isolated,
            'isolation_reasons': isolation_reasons,
            'branch': target_branch,
            'rollback_patch': write_patch_plan(path, rollback_dir, args.task_id, index),
        }
        if path.exists() and not args.dry_run and not blockers:
            result = run_command(['git', 'worktree', 'remove', '--force', str(path)], repo_root)
            action['git_worktree_remove'] = result
            if result.get('returncode') != 0:
                blockers.append(
                    {'id': 'git_worktree_remove_failed', 'path': str(path), 'stderr': result.get('stderr', '')}
                )
        actions.append(action)

    lock_release = release_locks(repo_root, args.run_id, args.task_id, dry_run=args.dry_run or bool(blockers))
    status = 'blocked' if blockers else ('dry_run' if args.dry_run else 'rolled_back')
    report = {
        'schema_version': '1.0',
        'generated_by': 'rollback_task.py',
        'generated_at': utc_now(),
        'workspace': str(repo_root),
        'run_id': args.run_id,
        'task_id': args.task_id,
        'status': status,
        'rule': 'rollback_may_only_remove_managed_worktrees_and_release_task_locks',
        'rollback_plan': {
            'default_mode': 'dry_run',
            'destructive_git_commands_allowed': [],
            'git_reset_hard_allowed': False,
            'delete_business_source_allowed': False,
            'actual_remove_requires': [
                '--yes',
                'isolated_worktree',
                'not_current_or_main_branch_or_second_confirmation',
            ],
        },
        'managed_worktree_root': str(managed_root),
        'targets': [str(path) for path in targets],
        'actions': actions,
        'lock_release': lock_release,
        'blockers': blockers,
        'safety': {
            'git_reset_hard_used': False,
            'project_source_deletion_allowed': False,
            'merge_deploy_release_authorized': False,
        },
    }
    write_json(repo_root / '.zoo-agent' / 'runs' / args.run_id / 'rollback' / f'{safe_name(args.task_id)}.json', report)
    return (0 if not blockers else 20), report


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Rollback a task by discarding managed worktrees and releasing task locks.'
    )
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--confirm-current-branch', action='store_true')
    args = parser.parse_args()
    code, report = rollback(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
