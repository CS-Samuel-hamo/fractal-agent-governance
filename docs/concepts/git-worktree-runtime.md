# Git Worktree Runtime

The worktree runtime isolates parallel exploration and uses path locks plus merge queues for controlled integration.

Parallel execution is allowed only after branch contracts exist and the scheduler has generated:

- `branch-schedule.json`
- `worktree-map.json`
- `path-locks.json`
- `resource-locks.json`
- `merge-queue.json`
- `parent-aggregation-matrices.json`
- `parallel-metrics.json`
- `parallel-execution-report.md`

The runtime may schedule safe branches in the same parallel phase, but final integration is serialized through parent aggregation and merge queue.

This project does not automatically launch multiple Codex workers in the background. It produces and validates the safe schedule; an orchestrator or user then starts bounded workers in the assigned worktrees.
