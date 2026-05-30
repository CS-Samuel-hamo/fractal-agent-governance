# Correct Governed Approach

1. Detect `data_source_mismatch`.
2. Record an obligation for source semantics.
3. Choose one implementation pattern:
   - adapter that wraps cached and live sources behind a stable interface
   - source selector that chooses cached or live per segment
   - provider injection that passes the source explicitly into the proc
4. Add behavior tests:
   - existing cached segment still uses cached branch-state
   - new live segment reads live branch-state
   - mixed-source response is documented
5. Escalate if the task does not define freshness, consistency, or fallback semantics.

Toy implementation sketch:

```ts
const summary = ProcBranchSummary(branchId, {
  sourceProvider: {
    defaultSource: cachedBranchState,
    liveSegmentSource: liveBranchState
  }
});
```

The point is not this exact API. The point is making the source choice explicit and testable.
