# Runtime Backbone

All governance capabilities must attach to the runtime backbone:

`Goal -> Run -> Project Context -> Obligations -> Branch Tree -> Worktree Schedule -> Execution -> Evidence -> Gates -> Review -> Parent Aggregation -> Merge Queue -> Integration -> Metrics -> Lessons`

Unique sources of truth:

- goal-contract: target facts
- run-ledger: process facts
- project-profile: project facts
- obligation-ledger: implicit work facts
- branch-state: fractal facts
- worktree-map: worktree and git branch facts
- path-locks: file ownership facts
- quality-gate: quality facts
- diagnostics-report: IDE diagnostics facts
- review-report: review facts
- parent-aggregation: parent branch aggregation facts
- merge-queue: integration queue facts
- artifact-graph: artifact version facts
- metrics: outcome facts
- lesson-store: learning facts

No artifact, no transition:

- no goal contract: no planning
- no project profile: no coding
- no obligation ledger: no execution
- no branch contract: no child task
- no worktree-map: no concurrent coding
- no path-locks: no parallel branch execution
- no completion evidence: no review
- no quality gate: no integration
- no parent aggregation: no final integration
- no merge-queue: no merging parallel branch outputs
- no event plus regression: no rules/skills change

Every artifact must include `run_id`, `goal_id`, applicable `branch_id`, `created_by_mode`, `model`, `created_at`, `input_artifacts`, `output_artifacts`, and `gate_status`.
