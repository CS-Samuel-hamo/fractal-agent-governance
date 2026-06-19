# Big Task Readiness Verdicts

- `READY_FOR_DECOMPOSITION_ONLY`: generate contracts only; no leaf execution.
- `READY_FOR_LEAF_DRY_RUN`: leaf tasks can be dry-run/manual task packs.
- `READY_FOR_LEAF_ACTUAL_WITH_CONFIRMATION`: only ready low-risk leaves may run with explicit user confirmation.
- `BLOCKED_NEEDS_ARCHITECTURE`: architecture is too unknown for execution.
- `BLOCKED_PROJECT_NOT_READY`: project readiness blocks execution.
- `BLOCKED_HIGH_RISK_HUMAN_GATE`: GPT/human gate required.
- `BLOCKED_BACKEND_UNHEALTHY`: Codex actual execution is disabled.
- `BLOCKED_GOAL_UNCLEAR`: set an explicit big task goal.
- `BLOCKED_TESTABILITY_UNKNOWN`: no leaf actual execution.
- `BLOCKED_ROLLBACK_UNKNOWN`: no leaf actual execution.
