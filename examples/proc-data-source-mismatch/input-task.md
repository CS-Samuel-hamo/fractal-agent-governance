# Input Task

Use existing `ProcBranchSummary`, but one segment must read from live branch-state instead of cached branch-state.

Assumptions for the toy fixture:

- `ProcBranchSummary` currently reads from `cachedBranchState`.
- The new segment requires `liveBranchState`.
- It is unclear whether freshness or historical consistency is more important.

Risk:

- Reusing the procedure without changing its source selection could silently return stale data.
