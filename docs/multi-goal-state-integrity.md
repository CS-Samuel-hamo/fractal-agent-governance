# Multi-goal State Integrity

Agent Runtime 0.7.2 makes multi-goal state an owned runtime object instead of a file that any module may rewrite.

The bug fixed by this policy was observed in the 0.7.1 controlled production test: after parent aggregation and the goal loop ran, the multi-goal state preserved the list of goals but reset priority, blocked/backlog status, and resource usage. The root cause was a single-goal completion result being written directly to `.zoo-agent/goal/goal_state.json`.

The invariant is simple: big-task, aggregation, scheduler, conflict, and loop modules may propose state changes, but only `scripts/goal_state_manager.py` may apply them to the canonical multi-goal state.

Runtime files:

- Canonical state: `.zoo-agent/goal/goal_state.json`
- Legacy mirror: `.zoo-agent/goal_state.json`
- Last applied patch: `.zoo-agent/goal/last-applied-state-patch.json`
- Human diff: `.zoo-agent/goal/goal-state-diff.md`
- Run-scoped proposals/results: `.zoo-agent/runs/<run-id>/`

Production rule: if a module needs to change goal scheduling state, it must emit a state patch with an explicit reason. Silent reconstruction of the goal list is not allowed.
