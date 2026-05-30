# Merge Queue Policy

Runtime artifact: `.zoo-agent/runs/<run-id>/merge-queue.json`

Parallel branches do not merge directly. They enqueue only after quality gate pass, review pass, path-lock pass, and no high/critical open risk. Merge queue order follows dependency graph and parent aggregation. Integrator may only make final decision after parent aggregation passes.
