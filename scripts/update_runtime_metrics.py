#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


METRIC_KEYS = [
    'fast_path_rate',
    'parallel_execution_rate',
    'governed_path_rate',
    'codex_latency',
    'fast_path_pre_codex_overhead_ms',
    'codex_execution_latency',
    'doc_overproduction_rate',
    'doc_only_task_rate',
    'code_delivery_rate',
    'parallel_denial_count',
    'loop_converged_count',
    'local_optimization_deferred_count',
]


def update_metrics(
    project: Path,
    *,
    path: str,
    codex_latency: float = 0.0,
    fast_path_pre_codex_overhead_ms: float = 0.0,
    codex_execution_ms: float = 0.0,
    code_delivered: bool = False,
    doc_overproduction: bool = False,
    doc_only_task: bool = False,
    code_delivery_gate_failed: bool = False,
    parallel_denied: bool = False,
    loop_converged: bool = False,
    local_optimization_deferred: bool = False,
    status: str = '',
) -> dict[str, Any]:
    metrics_path = project / '.zoo-agent' / 'metrics' / 'agent-runtime-v4.json'
    payload = load_json(metrics_path)
    counters = payload.get('counters') if isinstance(payload.get('counters'), dict) else {}
    total = int(counters.get('total_runs') or 0) + 1
    path_counts = counters.get('path_counts') if isinstance(counters.get('path_counts'), dict) else {}
    path_counts[path] = int(path_counts.get(path) or 0) + 1

    latency_count = int(counters.get('codex_latency_count') or 0)
    latency_total = float(counters.get('codex_latency_total') or 0.0)
    if codex_latency > 0:
        latency_count += 1
        latency_total += codex_latency

    overhead_count = int(counters.get('fast_path_pre_codex_overhead_count') or 0)
    overhead_total = float(counters.get('fast_path_pre_codex_overhead_total_ms') or 0.0)
    if fast_path_pre_codex_overhead_ms > 0:
        overhead_count += 1
        overhead_total += fast_path_pre_codex_overhead_ms

    codex_execution_count = int(counters.get('codex_execution_count') or 0)
    codex_execution_total = float(counters.get('codex_execution_total_ms') or 0.0)
    if codex_execution_ms > 0:
        codex_execution_count += 1
        codex_execution_total += codex_execution_ms

    code_delivery_count = int(counters.get('code_delivery_count') or 0) + (1 if code_delivered else 0)
    doc_overproduction_count = int(counters.get('doc_overproduction_count') or 0) + (1 if doc_overproduction else 0)
    doc_only_task_count = int(counters.get('doc_only_task_count') or 0) + (1 if doc_only_task else 0)
    code_delivery_gate_fail_count = int(counters.get('code_delivery_gate_fail_count') or 0) + (1 if code_delivery_gate_failed else 0)
    parallel_denial_count = int(counters.get('parallel_denial_count') or 0) + (1 if parallel_denied else 0)
    loop_converged_count = int(counters.get('loop_converged_count') or 0) + (1 if loop_converged else 0)
    local_optimization_deferred_count = int(counters.get('local_optimization_deferred_count') or 0) + (
        1 if local_optimization_deferred else 0
    )

    counters.update(
        {
            'total_runs': total,
            'path_counts': path_counts,
            'codex_latency_count': latency_count,
            'codex_latency_total': round(latency_total, 3),
            'fast_path_pre_codex_overhead_count': overhead_count,
            'fast_path_pre_codex_overhead_total_ms': round(overhead_total, 3),
            'codex_execution_count': codex_execution_count,
            'codex_execution_total_ms': round(codex_execution_total, 3),
            'code_delivery_count': code_delivery_count,
            'doc_overproduction_count': doc_overproduction_count,
            'doc_only_task_count': doc_only_task_count,
            'code_delivery_gate_fail_count': code_delivery_gate_fail_count,
            'parallel_denial_count': parallel_denial_count,
            'loop_converged_count': loop_converged_count,
            'local_optimization_deferred_count': local_optimization_deferred_count,
        }
    )
    metrics = {
        'fast_path_rate': round(path_counts.get('fast', 0) / total, 4),
        'parallel_execution_rate': round(path_counts.get('parallel', 0) / total, 4),
        'governed_path_rate': round(path_counts.get('governed', 0) / total, 4),
        'codex_latency': round(latency_total / latency_count, 3) if latency_count else 0.0,
        'fast_path_pre_codex_overhead_ms': round(overhead_total / overhead_count, 3) if overhead_count else 0.0,
        'codex_execution_latency': round(codex_execution_total / codex_execution_count, 3) if codex_execution_count else 0.0,
        'doc_overproduction_rate': round(doc_overproduction_count / total, 4),
        'doc_only_task_rate': round(doc_only_task_count / total, 4),
        'code_delivery_rate': round(code_delivery_count / total, 4),
        'code_delivery_gate_fail_count': code_delivery_gate_fail_count,
        'parallel_denial_count': parallel_denial_count,
        'loop_converged_count': loop_converged_count,
        'local_optimization_deferred_count': local_optimization_deferred_count,
    }
    payload = {
        'schema_version': '1.0',
        'generated_by': 'update_runtime_metrics.py',
        'updated_at': utc_now(),
        'metric_keys': METRIC_KEYS,
        'latest_event': {
            'path': path,
            'status': status,
            'codex_latency': codex_latency,
            'fast_path_pre_codex_overhead_ms': fast_path_pre_codex_overhead_ms,
            'codex_execution_ms': codex_execution_ms,
            'code_delivered': code_delivered,
            'doc_overproduction': doc_overproduction,
            'doc_only_task': doc_only_task,
            'code_delivery_gate_failed': code_delivery_gate_failed,
            'parallel_denied': parallel_denied,
            'loop_converged': loop_converged,
            'local_optimization_deferred': local_optimization_deferred,
        },
        'counters': counters,
        'metrics': metrics,
        'targets': {
            'doc_overproduction_rate': 'decrease',
            'doc_only_task_rate': 'decrease_for_coding_tasks',
            'code_delivery_rate': 'increase',
            'code_delivery_gate_fail_count': 'tracks_coding_tasks_without_code_delivery',
            'fast_path_rate': 'increase_when_safe',
            'parallel_execution_rate': 'increase_only_for_independent_tasks',
            'governed_path_rate': 'reserved_for_complex_tasks',
            'codex_latency': 'keep_low',
            'fast_path_pre_codex_overhead_ms': 'keep_low',
            'codex_execution_latency': 'keep_low',
            'parallel_denial_count': 'increase_when_parallel_is_unsafe',
            'loop_converged_count': 'tracks_forced_convergence',
            'local_optimization_deferred_count': 'tracks_noncritical_followups_deferred_by_loop_convergence',
        },
    }
    write_json(metrics_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Update CLI-first runtime metrics.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--path', required=True, choices=['fast', 'parallel', 'governed'])
    parser.add_argument('--status', default='')
    parser.add_argument('--codex-latency', type=float, default=0.0)
    parser.add_argument('--fast-path-pre-codex-overhead-ms', type=float, default=0.0)
    parser.add_argument('--codex-execution-ms', type=float, default=0.0)
    parser.add_argument('--code-delivered', action='store_true')
    parser.add_argument('--doc-overproduction', action='store_true')
    parser.add_argument('--doc-only-task', action='store_true')
    parser.add_argument('--code-delivery-gate-failed', action='store_true')
    parser.add_argument('--parallel-denied', action='store_true')
    parser.add_argument('--loop-converged', action='store_true')
    parser.add_argument('--local-optimization-deferred', action='store_true')
    args = parser.parse_args()

    project = project_root(args.workspace)
    report = update_metrics(
        project,
        path=args.path,
        status=args.status,
        codex_latency=args.codex_latency,
        fast_path_pre_codex_overhead_ms=args.fast_path_pre_codex_overhead_ms,
        codex_execution_ms=args.codex_execution_ms,
        code_delivered=args.code_delivered,
        doc_overproduction=args.doc_overproduction,
        doc_only_task=args.doc_only_task,
        code_delivery_gate_failed=args.code_delivery_gate_failed,
        parallel_denied=args.parallel_denied,
        loop_converged=args.loop_converged,
        local_optimization_deferred=args.local_optimization_deferred,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
