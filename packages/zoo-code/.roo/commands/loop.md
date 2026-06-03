---
description: Check loop budget and convergence for a run branch.
argument-hint: <run-id branch-id>
mode: agent-orchestrator
---

Read and update `.zoo-agent/runs/<run-id>/loop-state.json`. Mark stalled when coverage, unknown count, quality gate trajectory, risk, owned paths, or required obligations do not improve. Two stalled rounds or one regressing round must escalate.
