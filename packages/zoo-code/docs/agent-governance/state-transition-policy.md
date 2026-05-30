# State Transition Policy

The allowed mainline state machine is:

`intake -> goal_bound -> project_profile_ready -> obligation_ready -> planned -> branch_scoped -> executing -> evidence_ready -> quality_gate_ready -> mechanical_review_ready -> semantic_review_ready -> parent_aggregated -> integration_ready -> integrated -> final_reported`

Failure branch:

`any_state -> blocked`

`blocked -> remediate | decompose | escalate | fallback | abort`

Recovery branch:

- `remediate -> executing`
- `decompose -> branch_scoped`
- `escalate -> blocked | fallback | abort`
- `fallback -> remediate | decompose | abort`

## Required Artifacts

- No goal contract: cannot enter `goal_bound` or planning.
- No project profile: cannot enter coding.
- No obligation ledger: cannot enter execution.
- No branch contract/state: cannot create child task or enter branch-scoped execution.
- No worktree-map: cannot start concurrent coding.
- No path-locks: cannot approve parallel execution.
- No completion evidence: cannot enter review.
- No quality gate: cannot enter integration.
- No parent aggregation: cannot enter final integration.
- No merge-queue: cannot merge parallel branch outputs.
- No event plus regression: cannot modify rules or skills.

`update-run-ledger.py` enforces state ordering. `check-runtime-consistency.py` audits artifact completeness, shared `run_id`, current-state consistency, skipped artifacts, stale gate inputs, and orphan branch/review/lesson artifacts.

Optional Zoo-native signals may be attached to any transition:

- `checkpoint_ref`
- `worktree_path`
- `git_diff_stat`
- `diagnostics_report`

If these signals are unavailable, record `unknown` instead of inventing values.
