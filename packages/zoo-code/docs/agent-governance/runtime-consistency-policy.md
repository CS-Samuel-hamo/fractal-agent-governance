# Runtime Consistency Policy

Runtime consistency checks prevent old plans from continuing after human intervention.

Required checks before resume:

- `TASKS.md` is not newer than `task-board.json`.
- `TASKS.md` is not newer than `redirect-plan.json`.
- `redirect-plan.json` has been applied to `branch-state.json`.
- Merge queue does not execute abandoned, redo-needed, or paused branches.
- Retained branches have evidence before parent aggregation.
- Root and parent aggregation nodes are not execution nodes.
- Resource locks have no unresolved conflicts.
- Parent aggregation exists before non-empty final merge queue.
- Open required obligations are closed, deferred, or escalated.
- Quality gate and diagnostics reference current evidence.

When checks fail, set `run-ledger.current_state = resume_blocked`, write a report, and provide minimal fix actions.
