# Task Readiness Gate

Leaf readiness verdicts:

- `READY_FOR_DRY_RUN`
- `READY_FOR_ACTUAL_CODEX`
- `READY_FOR_MANUAL_REVIEW`
- `BLOCKED_MISSING_ACCEPTANCE`
- `BLOCKED_MISSING_SCOPE`
- `BLOCKED_UNSTABLE_CONSUMES`
- `BLOCKED_HIGH_RISK`
- `BLOCKED_BACKEND_UNHEALTHY`
- `BLOCKED_TEST_POLICY_UNKNOWN`

Readiness pass does not mean parent aggregation pass.

## Required Evidence

- explicit objective and acceptance
- owned resources
- allowed files and denied files
- stable `consumes` dependencies
- test policy
- rollback note
- backend health if actual execution is requested

## Rules

- `READY_FOR_DRY_RUN` permits task-pack/manual review only.
- `READY_FOR_ACTUAL_CODEX` requires low risk, bounded scope, explicit permission, and backend health.
- `READY_FOR_MANUAL_REVIEW` is for review/research or policy-sensitive leaves.
- High-risk readiness is a governance success: it blocks unsafe execution rather than failing silently.
