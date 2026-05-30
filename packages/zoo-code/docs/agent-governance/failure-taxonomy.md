# Failure Taxonomy

| Code | Failure class | Symptom | Default owner | Governance intervention |
|---|---|---|---|---|
| F01 | Missing integration surface | Core function implemented but API/registry/task branch/export/test omitted | executor/reviewer | executor skill + review checklist |
| F02 | Existing pattern not mined | New enum/util/processor duplicates existing one | executor/planner | task template + pattern mining skill |
| F03 | Proc data-source mismatch | Existing Proc reused while special data source ignored | planner/executor/reviewer | Proc clause + data-source skill |
| F04 | Ambiguous contract | Executor made plausible but wrong assumption | planner | task-spec template refinement |
| F05 | Reviewer escape | Major issue present but review approved | reviewer | review checklist/regression prompt |
| F06 | Branch drift | Branch scope expands or child summaries diverge | branch-manager | branch protocol update |
| F07 | Version isolation failure | Worktree/checkpoint/branch misuse caused pollution | integrator | worktree playbook update |
| F08 | Model routing failure | Weak model used for planning/review/high-risk task | planner/curator | model routing matrix update |
| F09 | Governance overfit | Rule added too broadly and slows tasks | curator | rollback/narrow rule |
| F10 | Context contamination | Parent task receives too much child detail or stale state | branch-manager | summary contract refinement |
