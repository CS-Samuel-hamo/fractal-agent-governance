#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cross_project_store import store_dir, write_store  # noqa: E402
from runtime_common import load_json, project_root  # noqa: E402


TASK_TYPES = ['repo_scan', 'docs_update', 'code_edit', 'test_update', 'analysis', 'release_readiness']


def add_counter(rows: dict[tuple[str, str], dict[str, Any]], worker: str, task_type: str, *, success: bool = False, failure: bool = False, no_delivery: bool = False, fallback: bool = False, evidence: dict[str, Any] | None = None) -> None:
    key = (worker or 'unknown', task_type or 'unknown')
    row = rows.setdefault(
        key,
        {'worker_role': key[0], 'task_type': key[1], 'success_count': 0, 'failure_count': 0, 'no_delivery_count': 0, 'fallback_count': 0, 'confidence_values': [], 'evidence': []},
    )
    row['success_count'] += 1 if success else 0
    row['failure_count'] += 1 if failure else 0
    row['no_delivery_count'] += 1 if no_delivery else 0
    row['fallback_count'] += 1 if fallback else 0
    row['confidence_values'].append(0.9 if success else 0.3 if failure else 0.5)
    if evidence:
        row['evidence'].append(evidence)


def recommended_use(worker: str, row: dict[str, Any], unavailable: set[str]) -> str:
    if worker in unavailable:
        return 'unavailable'
    success = int(row.get('success_count') or 0)
    failure = int(row.get('failure_count') or 0) + int(row.get('no_delivery_count') or 0)
    if success >= 2 and success >= failure:
        return 'prefer'
    if failure > success:
        return 'avoid'
    return 'allow'


def build_worker_memory(project: Path) -> dict[str, Any]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    registry = load_json(project / '.zoo-agent' / 'workers' / 'worker_registry.json')
    unavailable = {str(item.get('provider') or item.get('name') or '') for item in registry.get('workers') or [] if isinstance(item, dict) and not item.get('available')}
    for worker in ['local_scanner', 'dry_run', 'mock', 'codex', 'claude', 'local']:
        for task in TASK_TYPES:
            add_counter(rows, worker, task)

    for relative in [
        '.zoo-agent/worker_dogfood/worker_router_dogfood_trace.json',
        '.zoo-agent/real_worker_dogfood/real_worker_dogfood_trace.json',
    ]:
        trace = load_json(project / relative)
        for run in trace.get('runs') or []:
            if not isinstance(run, dict):
                continue
            decision = run.get('routing_decision') if isinstance(run.get('routing_decision'), dict) else {}
            profile = run.get('task_profile') if isinstance(run.get('task_profile'), dict) else {}
            provider = str(decision.get('provider') or decision.get('selected_provider') or run.get('selected_worker') or '').replace('_worker', '')
            if run.get('selected_worker') == 'local_scanner_worker':
                provider = 'local_scanner'
            task_type = str(profile.get('task_type') or run.get('scenario') or 'analysis')
            outcome = str(run.get('outcome') or '')
            add_counter(rows, provider or 'unknown', task_type, success=outcome == 'pass', failure=outcome == 'fail', fallback=bool(run.get('fallback_used')), evidence={'source': relative, 'scenario': run.get('scenario')})

    memory = []
    for (worker, task), row in sorted(rows.items()):
        values = row.pop('confidence_values', [])
        memory.append(
            {
                **row,
                'avg_confidence': round(sum(values) / max(len(values), 1), 3),
                'recommended_use': recommended_use(worker, row, unavailable),
                'evidence': row.get('evidence', [])[:8],
            }
        )
    payload = {'generated_by': 'worker_performance_memory.py', 'worker_performance': memory}
    return write_store(project, 'worker_memory', payload)


def main() -> int:
    parser = argparse.ArgumentParser(description='Build local worker performance memory.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_worker_memory(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
