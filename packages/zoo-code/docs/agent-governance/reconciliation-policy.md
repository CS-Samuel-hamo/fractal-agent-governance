# Reconciliation Policy

After a branch completes, reconciliation must run before parent aggregation.

Reconciliation checks:

- Completion evidence.
- Obligation ledger.
- Quality gate.
- Diagnostics report.
- Resource locks.
- Worktree status.
- Branch output artifacts.
- Branch status legality.

Failed reconciliation blocks merge queue entry and returns to branch-manager for re-scope, serialization, fallback, or rollback planning.
