#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--goal-id", default="unknown")
    parser.add_argument("--task-type", default="unknown")
    parser.add_argument("--model-route", default="hybrid-gpt-deepseek")
    parser.add_argument("--final-status", default="unknown")
    parser.add_argument("--output", default=".zoo-agent/metrics/run-metrics.jsonl")
    parser.add_argument("--quality-gate-status", default="unknown")
    parser.add_argument("--review-verdict", default="unknown")
    parser.add_argument("--fallback-used", action="store_true")
    parser.add_argument("--escalation-used", action="store_true")
    parser.add_argument("--human-gate-used", action="store_true")
    parser.add_argument("--parallel-branch-count", type=int, default=0)
    parser.add_argument("--parallel-group-count", type=int, default=0)
    parser.add_argument("--parallel-utilization-rate", type=float, default=0.0)
    parser.add_argument("--parallel-conflict-count", type=int, default=0)
    parser.add_argument("--parent-aggregation-success-rate", default="unknown")
    for name in [
        "interrupt-count", "progress-snapshot-count", "redirect-count", "task-board-apply-count",
        "branches-retained", "branches-abandoned", "branches-redone", "branches-paused",
        "needs-user-decision-count", "stale-plan-prevented-count",
        "resume-safety-check-pass-count", "resume-safety-check-fail-count",
        "parallel-candidates-count", "parallel-denial-count", "resource-lock-conflict-count",
        "reconciliation-failure-count", "parent-aggregation-failure-count",
        "aggregation-diagnostics-failure-count", "merge-queue-reorder-count",
        "rollback-plan-generated-count",
    ]:
        parser.add_argument(f"--{name}", type=int, default=0)
    args = parser.parse_args()
    row = {
        "run_id": args.run_id,
        "goal_id": args.goal_id,
        "task_type": args.task_type,
        "model_route": args.model_route,
        "fractal_depth": 0,
        "branch_count": 1,
        "obligation_count": 0,
        "required_obligation_closed_count": 0,
        "deferred_obligation_count": 0,
        "escalated_obligation_count": 0,
        "quality_gate_status": args.quality_gate_status,
        "review_verdict": args.review_verdict,
        "rework_loops": 0,
        "escalation_used": args.escalation_used,
        "fallback_used": args.fallback_used,
        "human_gate_used": args.human_gate_used,
        "open_risks": 0,
        "final_status": args.final_status,
        "estimated_gpt_calls": 0,
        "estimated_deepseek_calls": 0,
        "parallel_branch_count": args.parallel_branch_count,
        "parallel_group_count": args.parallel_group_count,
        "parallel_utilization_rate": args.parallel_utilization_rate,
        "parallel_conflict_count": args.parallel_conflict_count,
        "parent_aggregation_success_rate": args.parent_aggregation_success_rate,
        "interrupt_count": args.interrupt_count,
        "progress_snapshot_count": args.progress_snapshot_count,
        "redirect_count": args.redirect_count,
        "task_board_apply_count": args.task_board_apply_count,
        "branches_retained": args.branches_retained,
        "branches_abandoned": args.branches_abandoned,
        "branches_redone": args.branches_redone,
        "branches_paused": args.branches_paused,
        "needs_user_decision_count": args.needs_user_decision_count,
        "stale_plan_prevented_count": args.stale_plan_prevented_count,
        "resume_safety_check_pass_count": args.resume_safety_check_pass_count,
        "resume_safety_check_fail_count": args.resume_safety_check_fail_count,
        "parallel_candidates_count": args.parallel_candidates_count,
        "parallel_denial_count": args.parallel_denial_count,
        "resource_lock_conflict_count": args.resource_lock_conflict_count,
        "reconciliation_failure_count": args.reconciliation_failure_count,
        "parent_aggregation_failure_count": args.parent_aggregation_failure_count,
        "aggregation_diagnostics_failure_count": args.aggregation_diagnostics_failure_count,
        "merge_queue_reorder_count": args.merge_queue_reorder_count,
        "rollback_plan_generated_count": args.rollback_plan_generated_count,
        "created_at": now(),
        "completed_at": now(),
    }
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps({"status": "pass", "output": str(out), "row": row}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
