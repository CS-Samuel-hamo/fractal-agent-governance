---
name: fractal-decomposition
description: Recursively decompose complex work into bounded branch nodes with contracts, dependencies, owned paths, and parent aggregation matrices.
version: 3.6.0
scope: global
applies_to: agent-planner
last_updated: 2026-05-30
deprecated_by: ""
---

# Fractal Decomposition

Input root objective, project profile, project map, architecture boundaries, risk signals, and existing patterns. Output branch tree, child contracts, dependency matrix, ownership matrix, risk matrix, integration order, and parent aggregation plan. Derive branch `owned_paths`, `shared_paths`, and resource-lock candidates from `.zoo-agent/project-map.json` when available. Apply split/no-split criteria, needs_decomposition handling, max_depth handling, and anti-local-optimization loop budgets.
