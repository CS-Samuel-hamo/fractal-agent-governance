# Parallel Branch Execution

Default execution is dependency ordered and sequential. Parallel branch execution requires GPT branch-manager/orchestrator decision and a generated branch schedule, path locks, and merge queue.

Parallel is forbidden when owned paths overlap, shared paths are undeclared, provides/consumes are unstable, risk is high/critical, security/auth/payment/PII/migration is involved, acceptance/verification is not independent, worktree isolation is missing, or path locks conflict.

Parallel coding must use Git worktree. Parallel branches enqueue to merge queue and cannot merge directly. Parent aggregation must pass before integrator. DeepSeek cannot decide parallel safety.
