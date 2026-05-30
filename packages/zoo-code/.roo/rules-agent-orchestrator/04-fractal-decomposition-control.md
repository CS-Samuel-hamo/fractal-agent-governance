# Fractal Decomposition Control

Orchestrator is root branch owner. Non-trivial tasks create a root branch first. Child tasks require branch_id, depth, owner_mode, owned_paths, provides, consumes, acceptance_criteria, and stop_conditions.

If a child returns `needs_decomposition`, stop executor flow and return to branch-manager. If depth exceeds `max_depth`, escalate to GPT final planner. Parent aggregation must pass before integrator.

Enforce anti-local-optimization budgets: remediation max 2, `needs_decomposition` max 1, then parent escalation. If acceptance criteria are satisfied, quality gate passes, mechanical review passes, and GPT review has no BLOCKER/MAJOR, route to parent aggregation. Done child branches are immutable unless parent creates a follow-up branch.
# v3.7 Fractal + Boomerang Control

The orchestrator uses Zoo Boomerang for subtask delegation and fractal governance for recursive control.

- simple task: record no-split rationale and avoid unnecessary child tasks
- complex task: create root branch before child delegation
- child returns `needs_decomposition` when scope exceeds contract, patterns conflict, test strategy is unknown, architecture boundary is unknown, data-source mismatch is unknown, integration surface is unclear, required obligation cannot close, or diff risk exceeds threshold
- branch-manager/GPT decides split, research, re-scope, escalate, fallback, or abort
- depth over `max_depth` requires GPT final planner/branch-manager approval
- parent aggregation must pass before integration
- if splitting stops improving, use escalate/fallback/abort
