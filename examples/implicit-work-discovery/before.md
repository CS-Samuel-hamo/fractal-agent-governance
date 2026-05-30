# Before: Literal Execution

The agent receives:

> Add field `blockedReason` to branch summary.

A literal implementation might only change:

```ts
type BranchSummary = {
  branchId: string;
  status: "ready" | "running" | "blocked";
  blockedReason?: string | null;
};
```

Missed work:

- The mapper may not populate the field.
- The API response fixture may not include blocked and unblocked cases.
- The schema may reject the new field.
- The UI may still show only generic blocked status.
- Compatibility behavior may be untested.
- The ambiguous "multiple blockers" case may remain undefined.

This is fast, but it is not governed.
