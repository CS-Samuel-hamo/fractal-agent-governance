# Fast Path Gate Policy

Fast path is a lightweight delivery gate, not a governed merge gate.

It checks only:

- route is `fast`
- scope guard passed
- delivery outcome is `delivered` or `no_op_with_evidence`
- tests are `passed`, `skipped_with_reason`, or `not_applicable`
- result evidence was collected
- no denied files were touched

It does not require:

- task-board evidence
- parent aggregation
- implementation queue
- governed reviewer
- curator or lesson extraction
- eval suite
- release or operational readiness
- full test matrix
- product documents

Review verdicts:

- `FAST_DELIVERED`
- `FAST_NO_DELIVERY`
- `FAST_NO_OP_ACCEPTED`
- `FAST_UNSAFE`
- `FAST_BLOCKED`
- `GOVERNED_REVIEW_REQUIRED`

README/docs tasks may use `tests_status = not_applicable`. Missing docs tests must not block a
docs-only fast delivery unless the project explicitly provides docs tests.

Fast gate reads `delivery-outcome.json`; it does not recalculate delivery from global worktree diff.
The accepted delivery files must come from the task delta captured after `task-baseline.json`.
