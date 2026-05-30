# Runtime State Machine

The orchestrator owns the state machine and advances only through run-ledger transitions.

Mainline:

`intake -> goal_bound -> project_profile_ready -> obligation_ready -> planned -> branch_scoped -> executing -> evidence_ready -> quality_gate_ready -> mechanical_review_ready -> semantic_review_ready -> parent_aggregated -> integration_ready -> integrated -> final_reported`

Failure branch:

`any_state -> blocked`

`blocked -> remediate | decompose | escalate | fallback | abort`

Control-plane commands may create or update artifacts, but `/agent-run` remains the only main workflow bus. `/eval` is external governance evaluation and does not enter the ordinary task path.

Before each state transition, the orchestrator must verify the required artifact exists, belongs to the same `run_id`, is recorded in artifact graph, and has the latest input lineage for downstream gates.

Zoo-native runtime signals are first-class artifacts or transition fields:

- Boomerang child summaries feed branch-state and completion evidence.
- Worktrees require worktree-map, path-locks, and branch schedule before parallel execution.
- Checkpoints are recorded as `checkpoint_ref` on run-ledger transitions when available.
- Diagnostics report is a quality signal and must be read before integration when present.
- Codebase indexing status is read from project-profile and affects pattern-discovery confidence.

The orchestrator must not use scattered chat context to advance a run when the run-ledger and artifact-graph do not support the transition.
