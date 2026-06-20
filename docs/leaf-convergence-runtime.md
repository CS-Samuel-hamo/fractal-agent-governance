# Leaf Convergence Runtime

Version: 0.5.1-leaf-convergence-runtime

## Purpose

Leaf tasks are decision units, not mandatory execution units. A leaf that cannot
execute must converge to one final resolution instead of re-entering unlimited
decomposition.

## State Machine

`leaf_state` is one of:

- `ready_for_codex_execution`
- `needs_refinement`
- `should_merge_to_parent`
- `should_defer`
- `should_collapse_to_micro_task`
- `blocked`

Final resolutions are:

- `execute`: the leaf may enter a bounded Codex execution queue after explicit
  confirmation and backend/scope checks.
- `refine`: allowed at most once; after refinement the leaf must resolve again.
- `merge`: the leaf has no independent execution value and returns to parent
  aggregation.
- `defer`: the leaf moves to follow-up backlog and no longer blocks the current
  run.
- `collapse`: the leaf becomes a bounded micro-task, bypassing further
  decomposition.

## Non-Negotiable Rules

- A leaf may not enter Codex without a final `execute` resolution.
- A leaf may refine at most once.
- A leaf may not re-enter big-task decomposition.
- Missing acceptance or missing scope triggers refinement once, then merge or
  defer.
- Unknown resource dependency is not independent.
- High-risk leaves defer to a human/GPT gate and never run Codex actual by
  default.

## Outputs

- `.zoo-agent/runs/<run-id>/leaf-convergence-report.json`
- `.zoo-agent/runs/<run-id>/leaf-resolution/leaves/<leaf-id>.json`
- `.zoo-agent/runs/<run-id>/follow-up-backlog.json`
- `.zoo-agent/runs/<run-id>/leaf-merge-to-parent.json`
- `.zoo-agent/runs/<run-id>/micro-tasks.json`
- `.zoo-agent/runs/<run-id>/leaf-execution-queue.json`
- `.zoo-agent/metrics/leaf-convergence.json`

## CLI and Scripts

- `agent decompose ...` now runs leaf convergence automatically.
- `python scripts/resolve_leaf_task.py --run-id <id> --leaf-id <leaf>`
- `python scripts/check_leaf_convergence.py --run-id <id> --refresh`

## Safety Boundary

Leaf convergence does not merge, push, delete worktrees, read secrets, or launch
Codex actual execution. It only classifies leaf outcomes and writes runtime
evidence.

