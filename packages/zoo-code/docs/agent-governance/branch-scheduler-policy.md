# Branch Scheduler Policy

The scheduler should actively look for safe parallel leaf branches, but never force parallelism.

Parallel execution requires:

- Leaf execution branch.
- Non-conflicting owned paths.
- Declared shared paths.
- Stable provides/consumes contracts.
- No high/critical or security/auth/payment/PII/migration risk.
- Independent acceptance criteria.
- Independent verification plan.
- Worktree isolation and checkpoint.
- Passing resource locks.
- GPT branch-manager or orchestrator approval.

`branch-schedule.json` must record both approved parallel groups and denial reasons.

Parallel completion always flows through reconciliation -> parent aggregation -> serial merge queue.
