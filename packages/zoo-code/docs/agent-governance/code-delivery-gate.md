# Code Delivery Gate

The code delivery gate prevents coding branches from being marked done when
they only produced documents or planning artifacts.

## Checks

- coding task has code, test, or config diff
- valid no-code reason exists when there is no implementation diff
- docs-only diff is accepted only for docs-only tasks
- implementation queue exists for coding work
- ready or done implementation item exists
- Codex task pack exists when execution is pending
- Codex result links to implementation item when collected
- scope guard is pass or a precise blocker exists
- tests pass, are deferred with reason, or are not applicable
- root-goal coverage increased or blocker is explicit

If the gate fails, the branch cannot enter parent aggregation, merge queue, or
`done` status.
