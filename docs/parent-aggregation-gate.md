# Parent Aggregation Gate

Parent aggregation decides whether a decomposed big task is ready for an integration worktree.

It checks root goal coverage, success criteria coverage, non-goal violations, leaf delivery outcomes, open obligations, blockers, resource conflicts, dependency satisfaction, tests, rollback readiness, integration order, no-delivery leaves, backend failures, and deferred local optimizations.

Passing aggregation does not merge. It only permits creating or proposing an integration worktree.

## Inputs

- big task contract
- leaf task contracts
- leaf delivery outcomes
- task baseline and task delta evidence
- scope guard and test reports
- semantic resource map and dependency schedule
- loop state

## Verdicts

- `READY_FOR_INTEGRATION_WORKTREE`: required coverage and leaf evidence are present.
- `NEEDS_LEAF_REDO`: required leaf failed, produced no delivery, or remains blocked.
- `NEEDS_REPLANNING`: goal coverage or dependency satisfaction is incomplete.
- `BLOCKED`: backend failure, unresolved blocker, or required evidence is missing.
- `HUMAN_DECISION_REQUIRED`: high-risk unresolved leaf or policy-sensitive decision remains.
- `LOOP_DIVERGING`: repeated decomposition or redo cannot improve coverage.

Parent aggregation never merges, pushes, deletes worktrees, or edits business code. It only records whether the next safe step is an integration worktree candidate.
