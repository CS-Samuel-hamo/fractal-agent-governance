#!/usr/bin/env python3
"""Cost tracking and dashboard for AI worker usage.

Tracks daily call counts and estimated costs per worker.
Integrates with the policy engine's cost limits and the cockpit display.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, write_json

# Estimated cost per call (in USD) — conservative estimates
WORKER_COST_ESTIMATES = {
    'claude_worker_stub': 0.03,
    'claude_code': 0.03,
    'codex_worker_existing_adapter': 0.01,
    'bounded_docs_writer': 0.001,
    'dry_run_worker': 0.0,
    'mock_worker': 0.0,
    'local_scanner_worker': 0.0,
}


def _usage_path(project: Path) -> Path:
    return project / '.zoo-agent' / 'cost' / 'daily_usage.json'


def record_call(project: Path, worker: str, duration_seconds: float = 0.0) -> dict[str, Any]:
    """Record a worker call for cost tracking."""
    path = _usage_path(project)
    usage = load_json(path) if path.exists() else {}
    today = __import__('datetime').date.today().isoformat()
    day = usage.get(today, {'calls': 0, 'cost': 0.0, 'by_worker': {}})
    day['calls'] = day.get('calls', 0) + 1
    cost = WORKER_COST_ESTIMATES.get(worker, 0.01)
    day['cost'] = round(day.get('cost', 0.0) + cost, 4)
    by_worker = day.get('by_worker', {})
    by_worker[worker] = by_worker.get(worker, 0) + 1
    day['by_worker'] = by_worker
    usage[today] = day
    write_json(path, usage)
    return {'date': today, 'calls': day['calls'], 'cost': day['cost'], 'worker': worker}


def get_daily_usage(project: Path, days: int = 7) -> list[dict[str, Any]]:
    """Get daily usage for the last N days."""
    path = _usage_path(project)
    usage = load_json(path) if path.exists() else {}
    from datetime import date, timedelta

    results = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        day = usage.get(d, {'calls': 0, 'cost': 0.0, 'by_worker': {}})
        results.append({'date': d, 'calls': day['calls'], 'cost': day['cost'], 'by_worker': day.get('by_worker', {})})
    return results


def get_usage_summary(project: Path) -> dict[str, Any]:
    """Get a summary of all usage for the cockpit dashboard."""
    daily = get_daily_usage(project, 7)
    total_calls = sum(d['calls'] for d in daily)
    total_cost = round(sum(d['cost'] for d in daily), 4)
    workers: dict[str, int] = {}
    for d in daily:
        for w, c in d.get('by_worker', {}).items():
            workers[w] = workers.get(w, 0) + c

    return {
        'total_calls_7d': total_calls,
        'total_cost_7d': total_cost,
        'daily': daily,
        'by_worker': workers,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Cost tracking for AI worker usage.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--summary', action='store_true', help='Show usage summary (7 days)')
    parser.add_argument(
        '--record', nargs=2, metavar=('WORKER', 'DURATION'), help='Record a call: --record worker_name duration_seconds'
    )
    args = parser.parse_args()

    project = project_root(args.workspace)

    if args.record:
        worker, duration = args.record[0], float(args.record[1])
        result = record_call(project, worker, duration)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    result = get_usage_summary(project)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
