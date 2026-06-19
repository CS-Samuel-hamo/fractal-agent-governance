# Parent Aggregation Gate

Parent aggregation decides whether a decomposed big task is ready for an integration worktree.

It checks root goal coverage, success criteria coverage, non-goal violations, leaf delivery outcomes, open obligations, blockers, resource conflicts, dependency satisfaction, tests, rollback readiness, integration order, no-delivery leaves, backend failures, and deferred local optimizations.

Passing aggregation does not merge. It only permits creating or proposing an integration worktree.
