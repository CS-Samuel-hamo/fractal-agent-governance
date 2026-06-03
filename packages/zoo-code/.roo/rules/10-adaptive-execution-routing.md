# Adaptive Execution Routing

All `/agent-run` requests must classify governance intensity before executor selection.

Level 0 and Level 1 default to fast path. They must not trigger full fractal decomposition, multi-role flow, curator update, eval suite, release readiness, or operational readiness unless a trigger appears.

Level 2 requires obligation ledger, GPT planner approval, bounded execution, quality gate, and GPT reviewer.

Level 3 requires fractal decomposition, branch schedule, worktree map, resource locks, Codex Task Pack per executable leaf branch, parent aggregation, and merge queue.

Level 4 requires full governance, GPT final planner, ADR/security/release/human gate, and Codex only for explicitly authorized bounded subtasks.

Executor routing is recorded in `.zoo-agent/runs/<run-id>/executor-selection.json`.
