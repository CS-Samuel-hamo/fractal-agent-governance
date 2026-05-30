# Runtime Artifact Map

Every runtime artifact must carry identity and lineage:

- `run_id`
- `goal_id`
- `branch_id` when applicable
- `created_by_mode`
- `model`
- `created_at`
- `input_artifacts`
- `output_artifacts`
- `gate_status`

## Unique Sources Of Truth

| Source | Meaning | Canonical Path |
| --- | --- | --- |
| goal-contract | target facts | `.zoo-agent/goals/<goal-id>.json` |
| run-ledger | process facts | `.zoo-agent/runs/<run-id>/run-ledger.json` |
| project-profile | project facts | `.zoo-agent/project-profile.json` |
| obligation-ledger | implicit work facts | `.zoo-agent/runs/<run-id>/obligation-ledger.json` |
| branch-state | fractal task facts | `.zoo-agent/runs/<run-id>/branch-state.json` |
| worktree-map | worktree and git branch facts | `.zoo-agent/runs/<run-id>/worktree-map.json` |
| path-locks | file ownership facts | `.zoo-agent/runs/<run-id>/path-locks.json` |
| quality-gate | quality facts | `.zoo-agent/runs/<run-id>/quality-gate.json` |
| diagnostics-report | IDE diagnostics facts | `.zoo-agent/runs/<run-id>/diagnostics-report.json` |
| review-report | review facts | `.zoo-agent/runs/<run-id>/review-report.json` |
| parent-aggregation | parent branch aggregation facts | `.zoo-agent/runs/<run-id>/parent-aggregation.json` |
| merge-queue | integration queue facts | `.zoo-agent/runs/<run-id>/merge-queue.json` |
| artifact-graph | artifact version facts | `.zoo-agent/runs/<run-id>/artifact-graph.json` |
| metrics | outcome facts | `.zoo-agent/metrics/run-metrics.jsonl` |
| lesson-store | learning facts | `.zoo-agent/lessons/lesson-index.json` |

## Artifact Graph Rules

`artifact-graph.json` records all artifacts consumed by review, integration, release, learning, and evaluation. A gate or review must reference the artifact versions it read. Reviewer, integrator, and curator cannot rely on untracked context.

Artifact entries should include:

```json
{
  "artifact_id": "quality-gate",
  "type": "quality_gate",
  "path": ".zoo-agent/runs/<run-id>/quality-gate.json",
  "run_id": "<run-id>",
  "goal_id": "<goal-id>",
  "branch_id": "root",
  "created_by_mode": "agent-executor",
  "model": "DeepSeek V4 Flash",
  "created_at": "",
  "input_artifacts": [],
  "output_artifacts": [],
  "gate_status": "pass"
}
```

Zoo native artifacts are represented as governance artifacts, not as hidden context:

- Boomerang child summaries become branch evidence.
- Worktrees become `worktree-map` entries.
- Checkpoints become `checkpoint_ref` fields on run-ledger transitions or checkpoint artifacts.
- Diagnostics become `diagnostics-report`.
- Codebase indexing status becomes a project-profile field.
- API profile and sticky model choices are recorded through `created_by_mode` and `model`; provider secrets are never read.
