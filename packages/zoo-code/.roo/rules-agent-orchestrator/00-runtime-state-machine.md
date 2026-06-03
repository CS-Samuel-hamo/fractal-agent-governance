# Runtime State Machine

The orchestrator owns the state machine and advances only through run-ledger transitions.

Mainline:

`intake -> goal_bound -> project_profile_ready -> obligation_ready -> planned -> branch_scoped -> executing -> evidence_ready -> quality_gate_ready -> mechanical_review_ready -> semantic_review_ready -> parent_aggregated -> integration_ready -> integrated -> final_reported`

Failure branch:

`any_state -> blocked`

`blocked -> remediate | decompose | escalate | fallback | abort`

User steering branch:

`active -> paused`

`paused -> progress_snapshot`

`progress_snapshot -> redirected`

`redirected -> replanning`

`replanning -> resume_safety_check`

`resume_safety_check -> resume_ready | resume_blocked`

`resume_ready -> planned | branch_scoped | executing`

`resume_blocked -> needs_user_decision | fallback | aborted`

Control-plane commands may create or update artifacts, but `/agent-run` remains the only main workflow bus. `/eval` is external governance evaluation and does not enter the ordinary task path.

`/progress` creates a read-only progress snapshot plus the human-editable `TASKS.md` task board. `/redirect` creates a non-coding redirect plan and may mark branches `retained`, `abandoned`, `redo_needed`, or `needs_user_decision`. If `TASKS.md` is edited, apply it before resume so branch-state, run-ledger, artifact-graph, worktree-map, resource-locks, and merge-queue agree. `/agent-run` must read redirect state and run `resume-safety-check.py` before continuing; it must not silently continue an old plan.

Before each state transition, the orchestrator must verify the required artifact exists, belongs to the same `run_id`, is recorded in artifact graph, and has the latest input lineage for downstream gates.

Zoo-native runtime signals are first-class artifacts or transition fields:

- Boomerang child summaries feed branch-state and completion evidence.
- Worktrees require worktree-map, path-locks/resource-locks, and branch schedule before parallel execution.
- Checkpoints are recorded as `checkpoint_ref` on run-ledger transitions when available.
- Diagnostics report is a quality signal and must be read before integration when present.
- Codebase indexing status is read from project-profile and affects pattern-discovery confidence.
- Task board state is read from `TASKS.md`, `task-board.json`, and `tasks/<branch-id>.md`; these files are the preferred user-editable plan surface for interrupted or long-running fractal tasks.

The orchestrator must not use scattered chat context to advance a run when the run-ledger and artifact-graph do not support the transition.

Stop rules:

- Stop does not automatically discard a run.
- Stop does not automatically clean worktrees.
- Stop does not automatically merge.
- After Stop, users may inspect progress through GUI or `/progress`.
- After Stop, users may redirect direction through GUI or `/redirect`.
- Stop is a steering mechanism, not project failure.
