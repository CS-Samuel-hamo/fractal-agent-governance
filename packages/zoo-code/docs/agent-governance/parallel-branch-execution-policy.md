# Parallel Branch Execution Policy

Default execution inside one orchestrator run is dependency ordered and sequential. Parallel branch execution is an explicit optimization, not a default.

## Parallel Eligibility

Branches may run concurrently only when all conditions are true:
- `owned_paths` do not overlap
- `shared_paths` are declared
- `provides` and `consumes` contracts are stable
- no branch has high or critical risk
- no branch touches security, auth, payment, PII, or migration work
- each branch has independent acceptance criteria
- each branch has independent verification plan
- each branch uses Git worktree isolation
- path locks have no conflict

Coding in parallel must use Git worktrees. Completed parallel branches enter merge queue and never merge directly. Parent aggregation must pass before integrator. DeepSeek cannot decide parallel safety; GPT branch-manager or orchestrator decides the parallel group.
