#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
from pathlib import Path

STALE_PATTERNS = [
    re.compile(r'\bstale\b', re.IGNORECASE),
    re.compile(r'\bblocked\b', re.IGNORECASE),
    re.compile(r'\bTODO\b'),
    re.compile(r'\bTBD\b'),
]


def utc_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


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


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def observed_task_ids(run_dir: Path) -> list[str]:
    ids: set[str] = set()
    for folder in ['dispatcher-runs', 'optimistic-runs']:
        for path in sorted((run_dir / folder).glob('*.json')):
            ids.add(path.stem)
            payload = load_json(path)
            selection = payload.get('selection') if isinstance(payload.get('selection'), dict) else {}
            route = payload.get('route_decision') if isinstance(payload.get('route_decision'), dict) else {}
            for key in [selection.get('task_id'), route.get('task_id'), payload.get('task_id')]:
                if key:
                    ids.add(str(key))
    for path in sorted((run_dir / 'codex-results').glob('*/result.json')):
        ids.add(path.parent.name)
        payload = load_json(path)
        if payload.get('task_id'):
            ids.add(str(payload['task_id']))
    for path in sorted((run_dir / 'fractal-workstreams').glob('*.json')):
        ids.add(path.stem)
        payload = load_json(path)
        if payload.get('task_id'):
            ids.add(str(payload['task_id']))
    return sorted(ids)


def board_paths(repo_root: Path, run_id: str) -> list[Path]:
    candidates = [
        repo_root / '.zoo-agent' / 'TASKS.md',
        repo_root / '.zoo-agent' / 'task-board.md',
        repo_root / '.zoo-agent' / 'runs' / run_id / 'TASKS.md',
        repo_root / '.zoo-agent' / 'runs' / run_id / 'task-board.md',
    ]
    return [path for path in candidates if path.exists()]


def scan_boards(paths: list[Path]) -> tuple[str, list[dict]]:
    chunks = []
    stale_lines = []
    for path in paths:
        text = path.read_text(encoding='utf-8', errors='replace')
        chunks.append(text)
        for line_no, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in STALE_PATTERNS):
                stale_lines.append({'path': str(path), 'line': line_no, 'text': line.strip()[:240]})
    return '\n'.join(chunks), stale_lines


def write_markdown(path: Path, payload: dict) -> None:
    lines = [
        f'# Task Board Consistency: {payload["run_id"]}',
        '',
        f'- status: {payload["status"]}',
        f'- observed_task_count: {len(payload.get("observed_task_ids") or [])}',
        f'- warning_count: {len(payload.get("warnings") or [])}',
        '',
        '## Warnings',
        '',
    ]
    if not payload.get('warnings'):
        lines.append('- none')
    else:
        for warning in payload['warnings']:
            lines.append(f'- {warning.get("id")}: {warning.get("message")}')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser(
        description='Check whether Zoo run task-board evidence matches observed run artifacts.'
    )
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--expect-task', action='append', default=[])
    ap.add_argument('--allow-missing-board', action='store_true')
    args = ap.parse_args()

    repo_root = git_root(Path(args.workspace).resolve())
    run_dir = repo_root / '.zoo-agent' / 'runs' / args.run_id
    observed = set(observed_task_ids(run_dir))
    observed.update(str(item) for item in args.expect_task if str(item))
    paths = board_paths(repo_root, args.run_id)
    board_text, stale_lines = scan_boards(paths)

    warnings = []
    if not paths and not args.allow_missing_board:
        warnings.append({'id': 'missing_task_board', 'message': 'No project or run task board file was found.'})

    missing = []
    if board_text:
        for task_id in sorted(observed):
            if task_id and task_id not in board_text:
                missing.append(task_id)
        if missing:
            warnings.append(
                {
                    'id': 'observed_tasks_missing_from_board',
                    'message': 'Observed run tasks are not mentioned in task-board files.',
                    'task_ids': missing,
                }
            )
    if stale_lines:
        warnings.append(
            {
                'id': 'task_board_stale_or_blocked_markers',
                'message': 'Task-board files contain stale, blocked, TODO, or TBD markers.',
                'lines': stale_lines[:20],
            }
        )

    payload = {
        'schema_version': '1.0',
        'generated_by': 'check_task_board_consistency.py',
        'generated_at': utc_now(),
        'run_id': args.run_id,
        'workspace': str(repo_root),
        'status': 'ok' if not warnings else 'warnings',
        'task_board_paths': [str(path) for path in paths],
        'observed_task_ids': sorted(observed),
        'warnings': warnings,
    }
    output = run_dir / 'task-board-consistency.json'
    write_json(output, payload)
    write_markdown(output.with_suffix('.md'), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not warnings else 10


if __name__ == '__main__':
    raise SystemExit(main())
