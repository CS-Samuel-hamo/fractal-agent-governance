# Metrics Policy

Each run appends `.zoo-agent/metrics/run-metrics.jsonl` with ids, task type, model route, fractal depth, branch count, obligation counts, quality gate status, review verdict, rework loops, escalation/fallback/human gate use, open risks, final status, estimated GPT calls, estimated DeepSeek calls, and timestamps.

Parallel scheduling also writes `.zoo-agent/runs/<run-id>/parallel-metrics.json` and may append `.zoo-agent/metrics/parallel-branch-metrics.jsonl` with parallel branch count, parallel group count, parallel utilization rate, conflict count, merge queue serialization, and parent aggregation success rate when known.

Metrics must not contain secrets or business-sensitive prose. They measure routing effectiveness, implicit obligation discovery, fractal depth, rework, fallback rate, and quality gate pass rate.

0.3.8.1 integration hardening metrics:

- `interrupt_count`
- `progress_snapshot_count`
- `redirect_count`
- `task_board_apply_count`
- `branches_retained`
- `branches_abandoned`
- `branches_redone`
- `branches_paused`
- `needs_user_decision_count`
- `stale_plan_prevented_count`
- `resume_safety_check_pass_count`
- `resume_safety_check_fail_count`
- `parallel_candidates_count`
- `parallel_groups_count`
- `parallel_denial_count`
- `parallel_conflict_count`
- `resource_lock_conflict_count`
- `reconciliation_failure_count`
- `parent_aggregation_failure_count`
- `aggregation_diagnostics_failure_count`
- `merge_queue_reorder_count`
- `rollback_plan_generated_count`
