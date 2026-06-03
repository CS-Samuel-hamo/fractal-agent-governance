# Merge Queue Policy

Integrator only considers branches from merge queue. Queue entries require completion evidence, obligation ledger closure/defer/escalation, diagnostics report, aggregation diagnostics, quality gate pass, review pass, path-lock/resource-lock pass, no high/critical risk, reconciliation pass, and parent aggregation readiness. Parallel branches never merge directly.

The integrator processes merge queue entries serially in recorded queue order. Parent aggregation must be complete before final integration. DeepSeek executor or integration clerk may draft evidence summaries but cannot decide merge safety or reorder the queue.

Integrator must reject any queue entry whose branch reconciliation status is not `pass`, parent aggregation status is not `pass`, branch status is `abandoned`/`redo_needed`/`paused`, or diagnostics show regression. Failed entries remain blocked until branch-manager re-scopes, serializes, falls back, or archives them.
