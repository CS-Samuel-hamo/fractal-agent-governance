# Zoo Boomerang Tasks vs Fractal Task Governance

Zoo Code Boomerang Tasks provide native task delegation:

- subtask delegation
- isolated subtask context
- parent pauses while child runs
- child returns summary
- specialized mode selection

Fractal Task Governance runs on top of Boomerang. It does not replace Boomerang; it controls when and how recursive delegation is safe.

## Fractal Additions

- recursive decomposition
- branch node schema
- `needs_decomposition`
- `max_depth`
- `loop_budget`
- branch ownership
- owned_paths, shared_paths, forbidden_paths
- provides and consumes contracts
- dependency graph
- parent aggregation matrices
- worktree scheduling
- path locks
- merge queue
- fallback ladder
- lesson loop

## Purpose

Fractal decomposition is not infinite splitting. It is not local endless optimization. Its purpose is to turn hard work into bounded child tasks that are simple, executable, verifiable, and rollback-aware.

Simple tasks do not split and must record no-split rationale. Complex tasks create a root branch. If a child task is still complex, the child returns `needs_decomposition` instead of forcing a local patch.

GPT branch-manager decides whether to split deeper based on evidence. If depth exceeds `max_depth`, escalate to GPT final planner or branch-manager. If deeper split does not improve progress, move to escalate, fallback, or abort.
