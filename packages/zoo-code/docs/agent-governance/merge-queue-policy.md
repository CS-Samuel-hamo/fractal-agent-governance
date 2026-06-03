# Merge Queue Policy

Runtime artifact: `.zoo-agent/runs/<run-id>/merge-queue.json`

Parallel branches do not merge directly. They enqueue only after completion evidence exists, obligation ledger is closed/deferred/escalated, diagnostics report exists, quality gate passes, review passes, path-lock check passes, and no high/critical open risk remains. Merge queue order follows dependency graph and parent aggregation. Integrator may only make final decision after parent aggregation passes.

The merge queue is serial even when branch execution was parallel. GPT integrator controls merge order. DeepSeek executor cannot approve merge safety or reorder queue entries.

A queue entry is not merge-ready unless branch reconciliation and parent aggregation both pass. If reconciliation fails, the queue item status becomes blocked and the branch must be rolled back, re-scoped, serialized, or archived before it can re-enter the queue.
