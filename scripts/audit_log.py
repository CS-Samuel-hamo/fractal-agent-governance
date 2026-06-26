#!/usr/bin/env python3
"""Append-only audit log for worker calls and project operations.

Each entry is timestamped and append-only (never modified after writing).
The log is structured as JSON Lines (.jsonl) for easy querying.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now


def audit_log_path(project: Path) -> Path:
    return project / '.zoo-agent' / 'audit' / 'audit_log.jsonl'


def log_event(
    project: Path,
    *,
    event_type: str,
    worker: str = '',
    task: str = '',
    files_changed: list[str] | None = None,
    result: str = '',
    duration_seconds: float = 0.0,
    cost: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a single audit event to the log.

    The log is append-only JSON Lines — each line is a complete JSON object.
    """
    entry: dict[str, Any] = {
        'timestamp': utc_now(),
        'event_type': event_type,
        'worker': worker,
        'task': task[:500] if task else '',
    }
    if files_changed:
        entry['files_changed'] = files_changed[:100]  # cap at 100 files
    if result:
        entry['result'] = result
    if duration_seconds:
        entry['duration_seconds'] = round(duration_seconds, 3)
    if cost:
        entry['cost'] = round(cost, 4)
    if metadata:
        entry['metadata'] = metadata

    path = audit_log_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    return entry


def query_log(
    project: Path, *, limit: int = 50, event_type: str = '', worker: str = '', since: str = ''
) -> list[dict[str, Any]]:
    """Query the audit log, returning the most recent entries first."""
    path = audit_log_path(project)
    if not path.exists():
        return []

    entries: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event_type and entry.get('event_type') != event_type:
                continue
            if worker and entry.get('worker') != worker:
                continue
            if since and entry.get('timestamp', '') < since:
                continue
            entries.append(entry)

    entries.reverse()
    return entries[:limit]


def daily_summary(project: Path) -> dict[str, Any]:
    """Aggregate audit log into a daily summary."""
    entries = query_log(project, limit=10000, since=utc_now()[:10])  # today
    total_calls = len(entries)
    by_worker: dict[str, int] = {}
    by_type: dict[str, int] = {}
    total_cost = 0.0
    files_changed: list[str] = []

    for entry in entries:
        w = entry.get('worker', 'unknown')
        by_worker[w] = by_worker.get(w, 0) + 1
        t = entry.get('event_type', 'unknown')
        by_type[t] = by_type.get(t, 0) + 1
        total_cost += entry.get('cost', 0.0)
        files_changed.extend(entry.get('files_changed', []))

    return {
        'date': utc_now()[:10],
        'total_calls': total_calls,
        'total_cost': round(total_cost, 4),
        'by_worker': by_worker,
        'by_type': by_type,
        'total_files_changed': len(set(files_changed)),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Append-only audit log.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--query', action='store_true', help='Query recent events')
    parser.add_argument('--summary', action='store_true', help='Show daily summary')
    parser.add_argument('--event-type', default='')
    parser.add_argument('--worker', default='')
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--log', nargs='*', help='Log an event: --log event_type worker task')
    args = parser.parse_args()

    project = project_root(args.workspace)

    if args.query:
        entries = query_log(project, limit=args.limit, event_type=args.event_type, worker=args.worker)
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return 0

    if args.summary:
        result = daily_summary(project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.log:
        parts = args.log
        event_type = parts[0] if len(parts) > 0 else 'manual'
        worker = parts[1] if len(parts) > 1 else ''
        task = ' '.join(parts[2:]) if len(parts) > 2 else ''
        entry = log_event(project, event_type=event_type, worker=worker, task=task)
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
