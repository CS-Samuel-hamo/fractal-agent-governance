# Parallel Branch Execution

Default integration is dependency ordered and sequential. At root goal planning time, GPT branch-manager/orchestrator must actively evaluate whether child branches can run in parallel and must generate a branch schedule, worktree map, path locks, merge queue, run-ledger entries, artifact-graph links, checkpoint refs, parent aggregation matrices, and parallel metrics before any concurrent work starts.

Parallel is forbidden when owned paths overlap, shared paths are undeclared, provides/consumes are unstable, risk is high/critical, security/auth/payment/PII/migration is involved, acceptance/verification is not independent, worktree isolation is missing, or path locks conflict.

Parallel coding must use Git worktree. Each branch must have a rollback checkpoint before executor edits. Parallel branches enqueue to merge queue and cannot merge directly. Parent aggregation must pass before integrator. DeepSeek cannot decide parallel safety or merge order.

After branch completion, orchestrator must reconcile actual changed file names against path locks and required artifacts with `scripts/reconcile-branch-completion.py`. Parent aggregation must pass `scripts/parent-aggregation-gate.py` before final integration. If either check fails, run `scripts/rollback-branch-worktree.py` to block merge, record checkpoint/worktree rollback plan, and return to branch-manager for re-scope, serialization, fallback, or abort.
