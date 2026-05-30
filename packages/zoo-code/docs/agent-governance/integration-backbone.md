# Integration Backbone

All governance lines attach to one runtime backbone:

`Goal -> Run -> Project Context -> Obligations -> Branch Tree -> Worktree Schedule -> Execution -> Evidence -> Gates -> Review -> Parent Aggregation -> Merge Queue -> Integration -> Metrics -> Lessons`

`/agent-run` is the only main workflow bus. Other slash commands are control-plane tools that create, update, or inspect runtime artifacts for that bus.

## Backbone Mapping

| Backbone Stage | Source Of Truth | Primary Artifact | Commands / Systems |
| --- | --- | --- | --- |
| Goal | goal-contract | `.zoo-agent/goals/<goal-id>.json` | `/goal`, `/agent-run` |
| Run | run-ledger | `.zoo-agent/runs/<run-id>/run-ledger.json` | `/agent-run`, `/status` |
| Project Context | project-profile | `.zoo-agent/project-profile.json` | project-profiler |
| Obligations | obligation-ledger | `.zoo-agent/runs/<run-id>/obligation-ledger.json` | executor, mechanical reviewer |
| Branch Tree | branch-state | `.zoo-agent/runs/<run-id>/branch-state.json` or docs branch-state | branch-manager, branch-clerk |
| Worktree Schedule | worktree-map / branch-schedule / path-locks | `.zoo-agent/runs/<run-id>/worktree-map.json`, `branch-schedule.json`, `path-locks.json` | branch-manager, worktree scripts |
| Execution | completion evidence | `.zoo-agent/runs/<run-id>/completion-evidence.md` | executor |
| Gates | quality-gate / diagnostics-report | `.zoo-agent/runs/<run-id>/quality-gate.json`, `diagnostics-report.json` | quality gate and diagnostics scripts |
| Review | review-report | `.zoo-agent/runs/<run-id>/review-report.json` | mechanical reviewer, reviewer |
| Aggregation | parent aggregation | `.zoo-agent/runs/<run-id>/parent-aggregation.json` | branch-manager |
| Merge Queue | merge-queue | `.zoo-agent/runs/<run-id>/merge-queue.json` | integration clerk, integrator |
| Integration | integration report | `.zoo-agent/runs/<run-id>/integration-report.json` | integrator |
| Metrics | metrics | `.zoo-agent/metrics/run-metrics.jsonl` | metrics scripts |
| Lessons | lesson-store | `.zoo-agent/lessons/lesson-index.json` | curator-draft, curator |

## Command Roles

Mainline command:
- `/agent-run`

Control-plane commands:
- `/goal`
- `/status`
- `/risk`
- `/loop`
- `/escalate`
- `/fallback`
- `/decision`
- `/release`
- `/incident`
- `/lesson`
- `/evolve`
- `/regression`

Evaluation/governance-maintenance command:
- `/eval`

`/eval` does not enter the ordinary task path. It measures governance behavior against fixtures and writes eval reports.

## No Artifact, No Transition

The orchestrator advances only from run-ledger state plus artifact-graph evidence. If a required artifact is missing, stale, from another run, or not listed in artifact-graph, the run must stop at the current state or move to `blocked`.

Additional v3.7 transition guards:

- no worktree-map: no concurrent coding
- no path-locks: no parallel branch execution
- no merge-queue: no merging parallel branch outputs
- no diagnostics-report where diagnostics were requested: quality signal is `unknown`
- no checkpoint_ref where rollback was required: fallback/abort must record why checkpoint was unavailable
- no codebase indexing status in project-profile: pattern discovery confidence is `unknown`
