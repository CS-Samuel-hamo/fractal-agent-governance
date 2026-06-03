# Runtime Backbone

All governance capabilities must attach to the runtime backbone:

`Goal -> Run -> Project Context -> Obligations -> Branch Tree -> Worktree Schedule -> Execution -> Evidence -> Gates -> Review -> Parent Aggregation -> Merge Queue -> Integration -> Metrics -> Lessons`

Unique sources of truth:

- goal-contract: target facts
- run-ledger: process facts
- project-charter: durable project mission, non-goals, quality bar, and human gates
- project-profile: project facts
- project-map: module, file, entrypoint, test, doc, and dependency facts
- architecture-boundaries: dependency direction and module layer facts
- obligation-ledger: implicit work facts
- branch-state: fractal facts
- worktree-map: worktree and git branch facts
- path-locks: file ownership facts
- resource-locks: path and semantic resource ownership facts
- quality-gate: quality facts
- diagnostics-report: IDE diagnostics facts
- review-report: review facts
- parent-aggregation: parent branch aggregation facts
- merge-queue: integration queue facts
- artifact-graph: artifact version facts
- metrics: outcome facts
- lesson-store: learning facts
- progress snapshot: user-visible run position facts
- redirect plan: user steering facts
- task board: human-editable user intent, compiled through parse/diff/apply before runtime facts change

No artifact, no transition:

- no goal contract: no planning
- no project charter: no non-trivial coding unless escalated as `charter_unknown`
- no project profile: no coding
- no project map: no multi-module or architecture-sensitive coding
- no obligation ledger: no execution
- no branch contract: no child task
- no worktree-map: no concurrent coding
- no path-locks: no parallel branch execution
- no resource-locks: no semantic-resource-safe parallel branch execution
- no architecture boundaries: no high-risk architecture change without GPT decision
- no completion evidence: no review
- no quality gate: no integration
- no parent aggregation: no final integration
- no merge-queue: no merging parallel branch outputs
- no event plus regression: no rules/skills change

User intervention artifacts:

- progress snapshot: `.zoo-agent/runs/<run-id>/progress.json`
- progress markdown: `.zoo-agent/runs/<run-id>/progress.md`
- progress tree: `.zoo-agent/runs/<run-id>/progress-tree.md`
- redirect plan: `.zoo-agent/runs/<run-id>/redirect-plan.json`
- redirect event: `.zoo-agent/runs/<run-id>/events/redirect-<timestamp>.json`
- task board: `.zoo-agent/runs/<run-id>/TASKS.md`
- task board projection: `.zoo-agent/runs/<run-id>/task-board.json`
- resume safety check: `.zoo-agent/runs/<run-id>/resume-safety-check.json`

0.3.8.1 hardening rule: after Stop, Redirect, or Apply Task Board, `/agent-run` must block stale plans, apply user intent through parse/diff/apply, run `resume-safety-check.py`, and continue only from `resume_ready`.

Every artifact must include `run_id`, `goal_id`, applicable `branch_id`, `created_by_mode`, `model`, `created_at`, `input_artifacts`, `output_artifacts`, and `gate_status`.
