# Big Task Readiness

Big Task Readiness decides whether a large request can be decomposed, dry-run at leaf level, or considered for explicitly confirmed low-risk leaf execution.

Inputs include the active goal, success criteria, non-goals, project readiness, backend profile, loop state, architecture knowledge, test capability, rollback capability, affected domains, and affected resources.

Missing goal blocks big task decomposition. Unknown test or rollback capability prevents leaf actual execution. Unhealthy backend prevents Codex actual execution. High or critical risk requires GPT/human gate.

## Required Checks

- `goal_id` must be present for decomposition. Big tasks do not silently create transient goals.
- `success_criteria` must be explicit enough to map to leaf task acceptance and parent aggregation coverage.
- `non_goals` should be present; absence is a warning because it weakens scope control.
- `architecture_known=false` with cross-domain impact keeps the task in `decomposition_only`.
- `test_capability=unknown` prevents leaf actual execution.
- `rollback_capability=unknown` prevents leaf actual execution.
- backend health other than a usable profile prevents Codex actual execution.
- high or critical risk requires GPT/human gate; generated leaves remain dry-run/manual review only.

## Verdicts

- `READY_FOR_DECOMPOSITION_ONLY`: generate contract, resource map, and leaf contracts only.
- `READY_FOR_LEAF_DRY_RUN`: leaf tasks can be dry-run/manual task packs.
- `READY_FOR_LEAF_ACTUAL_WITH_CONFIRMATION`: only low-risk, ready leaves may run actual, and only with explicit confirmation.
- `BLOCKED_GOAL_UNCLEAR`: no explicit active goal or goal id.
- `BLOCKED_PROJECT_NOT_READY`: project readiness has blocking state.
- `BLOCKED_HIGH_RISK_HUMAN_GATE`: human/GPT gate required before execution.
- `BLOCKED_BACKEND_UNHEALTHY`: backend cannot support actual execution.
- `BLOCKED_TESTABILITY_UNKNOWN`: test policy is too weak for actual execution.
- `BLOCKED_ROLLBACK_UNKNOWN`: rollback/worktree safety is too weak for actual execution.

The readiness gate does not merge, push, delete worktrees, or run Codex on the root task.
