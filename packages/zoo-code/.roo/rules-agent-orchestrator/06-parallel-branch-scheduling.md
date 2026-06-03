# Parallel Branch Scheduling

GPT orchestrator must ask branch-manager to evaluate parallel scheduling at root goal planning time for Level 3+ fractal work. The decision must be artifact-backed, even when the result is serial execution.

Required pre-execution artifacts:

- `.zoo-agent/runs/<run-id>/branch-schedule.json`
- `.zoo-agent/runs/<run-id>/worktree-map.json`
- `.zoo-agent/runs/<run-id>/path-locks.json`
- `.zoo-agent/runs/<run-id>/merge-queue.json`
- `.zoo-agent/runs/<run-id>/parent-aggregation-matrices.json`
- `.zoo-agent/runs/<run-id>/parallel-metrics.json`
- `.zoo-agent/runs/<run-id>/parallel-execution-report.md`

Use `scripts/schedule-parallel-branches.py` after branch contracts exist. The scheduler must write every branch decision to run-ledger and artifact-graph. Branches with conflicts, unknown dependency, max-depth pressure, or missing acceptance/verification must be scheduled serially or marked `needs_decomposition`.

Post-execution control:

- run `scripts/reconcile-branch-completion.py` for each completed branch
- run `scripts/parent-aggregation-gate.py` before any parent final integration
- run `scripts/rollback-branch-worktree.py` when reconciliation or aggregation fails

No branch may remain in merge queue as merge-ready after a failed reconciliation.
