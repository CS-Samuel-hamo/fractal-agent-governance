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
    'backend_latency',
    'fast_path_pre_backend_overhead_ms',
    'backend_execution_latency',
    'doc_overproduction_rate',
    'doc_only_task_rate',
    'code_delivery_rate',
    'parallel_denial_count',
    'backend_health_check_count',
    'backend_failure_count',
    'backend_failure_type',
    'no_delivery_count',
    'no_op_with_evidence_count',
    'loop_converged_count',
    'loop_stopped_count',
    'local_optimization_deferred_count',
    'manual_intervention_count',
    'leaf_refinement_count',
    'leaf_resolution_rate',
    'leaf_collapse_rate',
    'leaf_defer_rate',
    'leaf_merge_rate',
    'convergence_failure_rate',
    'backend_execution_from_leaf_rate',
    'goal_completion_rate',
    'loop_convergence_rate',
    'leaf_to_goal_contribution_ratio',
    'stuck_loop_rate',
    'over_decomposition_rate',
    'no_delivery_goal_impact',
    'backend_execution_success_rate',
    'goal_drift_frequency',
]


def update_metrics(
    project: Path,
    *,
    path: str,
    backend_latency: float = 0.0,
    fast_path_pre_backend_overhead_ms: float = 0.0,
    backend_execution_ms: float = 0.0,
    code_delivered: bool = False,
    doc_overproduction: bool = False,
    doc_only_task: bool = False,
    code_delivery_gate_failed: bool = False,
    parallel_denied: bool = False,
    backend_health_checked: bool = False,
    backend_failure: bool = False,
    backend_failure_type: str = '',
    no_delivery: bool = False,
    no_op_with_evidence: bool = False,
    loop_converged: bool = False,
    loop_stopped: bool = False,
    local_optimization_deferred: bool = False,
    manual_intervention: bool = False,
    leaf_refinement_count: int = 0,
    leaf_resolved: bool = False,
    leaf_collapsed: bool = False,
    leaf_deferred: bool = False,
    leaf_merged: bool = False,
    leaf_convergence_failure: bool = False,
    backend_execution_from_leaf: bool = False,
    goal_completed: bool = False,
    loop_converged_event: bool = False,
    stuck_loop: bool = False,
    over_decomposition: bool = False,
    no_delivery_goal_impact: int = 0,
    backend_execution_success: bool = False,
    goal_drift: bool = False,
    leaf_goal_contribution_count: int = 0,
    leaf_goal_total_count: int = 0,
    status: str = '',
) -> dict[str, Any]:
    metrics_path = project / '.zoo-agent' / 'metrics' / 'agent-runtime-v4.json'
    payload = load_json(metrics_path)
    counters = payload.get('counters') if isinstance(payload.get('counters'), dict) else {}
    total = int(counters.get('total_runs') or 0) + 1
    path_counts = counters.get('path_counts') if isinstance(counters.get('path_counts'), dict) else {}
    path_counts[path] = int(path_counts.get(path) or 0) + 1

    latency_count = int(counters.get('backend_latency_count') or 0)
    latency_total = float(counters.get('backend_latency_total') or 0.0)
    if backend_latency > 0:
        latency_count += 1
        latency_total += backend_latency

    overhead_count = int(counters.get('fast_path_pre_backend_overhead_count') or 0)
    overhead_total = float(counters.get('fast_path_pre_backend_overhead_total_ms') or 0.0)
    if fast_path_pre_backend_overhead_ms > 0:
        overhead_count += 1
        overhead_total += fast_path_pre_backend_overhead_ms

    backend_execution_count = int(counters.get('backend_execution_count') or 0)
    backend_execution_total = float(counters.get('backend_execution_total_ms') or 0.0)
    if backend_execution_ms > 0:
        backend_execution_count += 1
        backend_execution_total += backend_execution_ms

    code_delivery_count = int(counters.get('code_delivery_count') or 0) + (1 if code_delivered else 0)
    doc_overproduction_count = int(counters.get('doc_overproduction_count') or 0) + (1 if doc_overproduction else 0)
    doc_only_task_count = int(counters.get('doc_only_task_count') or 0) + (1 if doc_only_task else 0)
    code_delivery_gate_fail_count = int(counters.get('code_delivery_gate_fail_count') or 0) + (1 if code_delivery_gate_failed else 0)
    parallel_denial_count = int(counters.get('parallel_denial_count') or 0) + (1 if parallel_denied else 0)
    backend_health_check_count = int(counters.get('backend_health_check_count') or 0) + (1 if backend_health_checked else 0)
    backend_failure_count = int(counters.get('backend_failure_count') or 0) + (1 if backend_failure else 0)
    no_delivery_count = int(counters.get('no_delivery_count') or 0) + (1 if no_delivery else 0)
    no_op_with_evidence_count = int(counters.get('no_op_with_evidence_count') or 0) + (1 if no_op_with_evidence else 0)
    loop_converged_count = int(counters.get('loop_converged_count') or 0) + (1 if loop_converged else 0)
    loop_stopped_count = int(counters.get('loop_stopped_count') or 0) + (1 if loop_stopped else 0)
    local_optimization_deferred_count = int(counters.get('local_optimization_deferred_count') or 0) + (
        1 if local_optimization_deferred else 0
    )
    manual_intervention_count = int(counters.get('manual_intervention_count') or 0) + (1 if manual_intervention else 0)
    leaf_total_count = int(counters.get('leaf_total_count') or 0) + (
        1 if any([leaf_resolved, leaf_collapsed, leaf_deferred, leaf_merged, leaf_convergence_failure, backend_execution_from_leaf]) else 0
    )
    leaf_refinement_total = int(counters.get('leaf_refinement_count') or 0) + max(int(leaf_refinement_count or 0), 0)
    leaf_resolved_count = int(counters.get('leaf_resolved_count') or 0) + (1 if leaf_resolved else 0)
    leaf_collapse_count = int(counters.get('leaf_collapse_count') or 0) + (1 if leaf_collapsed else 0)
    leaf_defer_count = int(counters.get('leaf_defer_count') or 0) + (1 if leaf_deferred else 0)
    leaf_merge_count = int(counters.get('leaf_merge_count') or 0) + (1 if leaf_merged else 0)
    leaf_convergence_failure_count = int(counters.get('leaf_convergence_failure_count') or 0) + (1 if leaf_convergence_failure else 0)
    backend_execution_from_leaf_count = int(counters.get('backend_execution_from_leaf_count') or 0) + (1 if backend_execution_from_leaf else 0)
    goal_loop_total_count = int(counters.get('goal_loop_total_count') or 0) + (
        1 if any([goal_completed, loop_converged_event, stuck_loop, over_decomposition, goal_drift, leaf_goal_total_count, no_delivery_goal_impact]) else 0
    )
    goal_completed_count = int(counters.get('goal_completed_count') or 0) + (1 if goal_completed else 0)
    loop_convergence_event_count = int(counters.get('loop_convergence_event_count') or 0) + (1 if loop_converged_event else 0)
    stuck_loop_count = int(counters.get('stuck_loop_count') or 0) + (1 if stuck_loop else 0)
    over_decomposition_count = int(counters.get('over_decomposition_count') or 0) + (1 if over_decomposition else 0)
    no_delivery_goal_impact_count = int(counters.get('no_delivery_goal_impact_count') or 0) + max(int(no_delivery_goal_impact or 0), 0)
    backend_execution_success_count = int(counters.get('backend_execution_success_count') or 0) + (1 if backend_execution_success else 0)
    goal_drift_count = int(counters.get('goal_drift_count') or 0) + (1 if goal_drift else 0)
    leaf_goal_contribution_total = int(counters.get('leaf_goal_contribution_count') or 0) + max(int(leaf_goal_contribution_count or 0), 0)
    leaf_goal_total = int(counters.get('leaf_goal_total_count') or 0) + max(int(leaf_goal_total_count or 0), 0)
    failure_types = counters.get('backend_failure_types') if isinstance(counters.get('backend_failure_types'), dict) else {}
    if backend_failure and backend_failure_type:
        failure_types[backend_failure_type] = int(failure_types.get(backend_failure_type) or 0) + 1

    counters.update(
        {
            'total_runs': total,
            'path_counts': path_counts,
            'backend_latency_count': latency_count,
            'backend_latency_total': round(latency_total, 3),
            'fast_path_pre_backend_overhead_count': overhead_count,
            'fast_path_pre_backend_overhead_total_ms': round(overhead_total, 3),
            'backend_execution_count': backend_execution_count,
            'backend_execution_total_ms': round(backend_execution_total, 3),
            'code_delivery_count': code_delivery_count,
            'doc_overproduction_count': doc_overproduction_count,
            'doc_only_task_count': doc_only_task_count,
            'code_delivery_gate_fail_count': code_delivery_gate_fail_count,
            'parallel_denial_count': parallel_denial_count,
            'backend_health_check_count': backend_health_check_count,
            'backend_failure_count': backend_failure_count,
            'backend_failure_types': failure_types,
            'no_delivery_count': no_delivery_count,
            'no_op_with_evidence_count': no_op_with_evidence_count,
            'loop_converged_count': loop_converged_count,
            'loop_stopped_count': loop_stopped_count,
            'local_optimization_deferred_count': local_optimization_deferred_count,
            'manual_intervention_count': manual_intervention_count,
            'leaf_total_count': leaf_total_count,
            'leaf_refinement_count': leaf_refinement_total,
            'leaf_resolved_count': leaf_resolved_count,
            'leaf_collapse_count': leaf_collapse_count,
            'leaf_defer_count': leaf_defer_count,
            'leaf_merge_count': leaf_merge_count,
            'leaf_convergence_failure_count': leaf_convergence_failure_count,
            'backend_execution_from_leaf_count': backend_execution_from_leaf_count,
            'goal_loop_total_count': goal_loop_total_count,
            'goal_completed_count': goal_completed_count,
            'loop_convergence_event_count': loop_convergence_event_count,
            'stuck_loop_count': stuck_loop_count,
            'over_decomposition_count': over_decomposition_count,
            'no_delivery_goal_impact_count': no_delivery_goal_impact_count,
            'backend_execution_success_count': backend_execution_success_count,
            'goal_drift_count': goal_drift_count,
            'leaf_goal_contribution_count': leaf_goal_contribution_total,
            'leaf_goal_total_count': leaf_goal_total,
        }
    )
    metrics = {
        'fast_path_rate': round(path_counts.get('fast', 0) / total, 4),
        'parallel_execution_rate': round(path_counts.get('parallel', 0) / total, 4),
        'governed_path_rate': round(path_counts.get('governed', 0) / total, 4),
        'backend_latency': round(latency_total / latency_count, 3) if latency_count else 0.0,
        'fast_path_pre_backend_overhead_ms': round(overhead_total / overhead_count, 3) if overhead_count else 0.0,
        'backend_execution_latency': round(backend_execution_total / backend_execution_count, 3) if backend_execution_count else 0.0,
        'doc_overproduction_rate': round(doc_overproduction_count / total, 4),
        'doc_only_task_rate': round(doc_only_task_count / total, 4),
        'code_delivery_rate': round(code_delivery_count / total, 4),
        'code_delivery_gate_fail_count': code_delivery_gate_fail_count,
        'parallel_denial_count': parallel_denial_count,
        'backend_health_check_count': backend_health_check_count,
        'backend_failure_count': backend_failure_count,
        'backend_failure_type': backend_failure_type,
        'no_delivery_count': no_delivery_count,
        'no_op_with_evidence_count': no_op_with_evidence_count,
        'loop_converged_count': loop_converged_count,
        'loop_stopped_count': loop_stopped_count,
        'local_optimization_deferred_count': local_optimization_deferred_count,
        'manual_intervention_count': manual_intervention_count,
        'leaf_refinement_count': leaf_refinement_total,
        'leaf_resolution_rate': round(leaf_resolved_count / leaf_total_count, 4) if leaf_total_count else 0.0,
        'leaf_collapse_rate': round(leaf_collapse_count / leaf_total_count, 4) if leaf_total_count else 0.0,
        'leaf_defer_rate': round(leaf_defer_count / leaf_total_count, 4) if leaf_total_count else 0.0,
        'leaf_merge_rate': round(leaf_merge_count / leaf_total_count, 4) if leaf_total_count else 0.0,
        'convergence_failure_rate': round(leaf_convergence_failure_count / leaf_total_count, 4) if leaf_total_count else 0.0,
        'backend_execution_from_leaf_rate': round(backend_execution_from_leaf_count / leaf_total_count, 4) if leaf_total_count else 0.0,
        'goal_completion_rate': round(goal_completed_count / goal_loop_total_count, 4) if goal_loop_total_count else 0.0,
        'loop_convergence_rate': round(loop_convergence_event_count / goal_loop_total_count, 4) if goal_loop_total_count else 0.0,
        'leaf_to_goal_contribution_ratio': round(leaf_goal_contribution_total / leaf_goal_total, 4) if leaf_goal_total else 0.0,
        'stuck_loop_rate': round(stuck_loop_count / goal_loop_total_count, 4) if goal_loop_total_count else 0.0,
        'over_decomposition_rate': round(over_decomposition_count / goal_loop_total_count, 4) if goal_loop_total_count else 0.0,
        'no_delivery_goal_impact': no_delivery_goal_impact_count,
        'backend_execution_success_rate': round(backend_execution_success_count / max(backend_execution_count, 1), 4) if backend_execution_count else 0.0,
        'goal_drift_frequency': round(goal_drift_count / goal_loop_total_count, 4) if goal_loop_total_count else 0.0,
    }
    payload = {
        'schema_version': '1.0',
        'generated_by': 'update_runtime_metrics.py',
        'updated_at': utc_now(),
        'metric_keys': METRIC_KEYS,
        'latest_event': {
            'path': path,
            'status': status,
            'backend_latency': backend_latency,
            'fast_path_pre_backend_overhead_ms': fast_path_pre_backend_overhead_ms,
            'backend_execution_ms': backend_execution_ms,
            'code_delivered': code_delivered,
            'doc_overproduction': doc_overproduction,
            'doc_only_task': doc_only_task,
            'code_delivery_gate_failed': code_delivery_gate_failed,
            'parallel_denied': parallel_denied,
            'backend_health_checked': backend_health_checked,
            'backend_failure': backend_failure,
            'backend_failure_type': backend_failure_type,
            'no_delivery': no_delivery,
            'no_op_with_evidence': no_op_with_evidence,
            'loop_converged': loop_converged,
            'loop_stopped': loop_stopped,
            'local_optimization_deferred': local_optimization_deferred,
            'manual_intervention': manual_intervention,
            'leaf_refinement_count': leaf_refinement_count,
            'leaf_resolved': leaf_resolved,
            'leaf_collapsed': leaf_collapsed,
            'leaf_deferred': leaf_deferred,
            'leaf_merged': leaf_merged,
            'leaf_convergence_failure': leaf_convergence_failure,
            'backend_execution_from_leaf': backend_execution_from_leaf,
            'goal_completed': goal_completed,
            'loop_converged_event': loop_converged_event,
            'stuck_loop': stuck_loop,
            'over_decomposition': over_decomposition,
            'no_delivery_goal_impact': no_delivery_goal_impact,
            'backend_execution_success': backend_execution_success,
            'goal_drift': goal_drift,
            'leaf_goal_contribution_count': leaf_goal_contribution_count,
            'leaf_goal_total_count': leaf_goal_total_count,
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
            'backend_latency': 'keep_low',
            'fast_path_pre_backend_overhead_ms': 'keep_low',
            'backend_execution_latency': 'keep_low',
            'parallel_denial_count': 'increase_when_parallel_is_unsafe',
            'backend_health_check_count': 'avoid_full_health_on_every_fast_task',
            'backend_failure_count': 'backend_failures_do_not_pollute_task_delivery_metrics',
            'no_delivery_count': 'task_delivery_failures_without_backend_failure',
            'no_op_with_evidence_count': 'accepted_noop_when_evidence_is_specific',
            'loop_converged_count': 'tracks_forced_convergence',
            'loop_stopped_count': 'tracks_loss_control_stops',
            'local_optimization_deferred_count': 'tracks_noncritical_followups_deferred_by_loop_convergence',
            'manual_intervention_count': 'tracks_required_human_intervention',
            'leaf_refinement_count': 'tracks bounded one-pass leaf refinement',
            'leaf_resolution_rate': 'target 100 percent final execute/merge/defer/collapse resolution',
            'leaf_collapse_rate': 'tracks leaves collapsed to bounded micro-tasks',
            'leaf_defer_rate': 'tracks leaves deferred to backlog instead of blocking the run',
            'leaf_merge_rate': 'tracks leaves merged back to parent aggregation',
            'convergence_failure_rate': 'target 0 unresolved leaf convergence failures',
            'backend_execution_from_leaf_rate': 'tracks backend execution entered through resolved leaf contracts',
            'goal_completion_rate': 'tracks goals completed by parent aggregation evidence',
            'loop_convergence_rate': 'tracks loops that stop because the goal is complete',
            'leaf_to_goal_contribution_ratio': 'tracks delivered leaf contribution to goal progress',
            'stuck_loop_rate': 'decrease; detects loops that cannot progress',
            'over_decomposition_rate': 'decrease; detects excessive leaf decomposition',
            'no_delivery_goal_impact': 'decrease; no_delivery leafs should not count as goal progress',
            'backend_execution_success_rate': 'increase for actual leaf execution',
            'goal_drift_frequency': 'decrease; drift should trigger warning or stop',
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
    parser.add_argument('--backend-health-checked', action='store_true')
    parser.add_argument('--backend-failure', action='store_true')
    parser.add_argument('--backend-failure-type', default='')
    parser.add_argument('--no-delivery', action='store_true')
    parser.add_argument('--no-op-with-evidence', action='store_true')
    parser.add_argument('--loop-converged', action='store_true')
    parser.add_argument('--loop-stopped', action='store_true')
    parser.add_argument('--local-optimization-deferred', action='store_true')
    parser.add_argument('--manual-intervention', action='store_true')
    parser.add_argument('--leaf-refinement-count', type=int, default=0)
    parser.add_argument('--leaf-resolved', action='store_true')
    parser.add_argument('--leaf-collapsed', action='store_true')
    parser.add_argument('--leaf-deferred', action='store_true')
    parser.add_argument('--leaf-merged', action='store_true')
    parser.add_argument('--leaf-convergence-failure', action='store_true')
    parser.add_argument('--codex-execution-from-leaf', action='store_true')
    args = parser.parse_args()

    project = project_root(args.workspace)
    report = update_metrics(
        project,
        path=args.path,
        status=args.status,
        backend_latency=args.backend_latency,
        fast_path_pre_backend_overhead_ms=args.fast_path_pre_backend_overhead_ms,
        backend_execution_ms=args.backend_execution_ms,
        code_delivered=args.code_delivered,
        doc_overproduction=args.doc_overproduction,
        doc_only_task=args.doc_only_task,
        code_delivery_gate_failed=args.code_delivery_gate_failed,
        parallel_denied=args.parallel_denied,
        backend_health_checked=args.backend_health_checked,
        backend_failure=args.backend_failure,
        backend_failure_type=args.backend_failure_type,
        no_delivery=args.no_delivery,
        no_op_with_evidence=args.no_op_with_evidence,
        loop_converged=args.loop_converged,
        loop_stopped=args.loop_stopped,
        local_optimization_deferred=args.local_optimization_deferred,
        manual_intervention=args.manual_intervention,
        leaf_refinement_count=args.leaf_refinement_count,
        leaf_resolved=args.leaf_resolved,
        leaf_collapsed=args.leaf_collapsed,
        leaf_deferred=args.leaf_deferred,
        leaf_merged=args.leaf_merged,
        leaf_convergence_failure=args.leaf_convergence_failure,
        backend_execution_from_leaf=args.backend_execution_from_leaf,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
