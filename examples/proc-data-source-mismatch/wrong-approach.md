# Wrong Approach

```ts
const summary = ProcBranchSummary(branchId);
return {
  ...summary,
  liveSegment: summary.segment
};
```

Why this fails:

- It directly calls `ProcBranchSummary`.
- It assumes the existing cached source is valid for the new live segment.
- It ignores the data source difference between cached branch-state and live branch-state.
- It has no behavior test proving freshness.
- It hides a semantic decision inside a convenience reuse.

This looks efficient, but it is a governance failure.
