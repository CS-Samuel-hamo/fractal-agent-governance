# Task Board Apply Protocol

Apply Task Board has three phases.

## Parse

Input:

- `.zoo-agent/runs/<run-id>/TASKS.md`
- `.zoo-agent/runs/<run-id>/tasks/*.md`

Output:

- `.zoo-agent/runs/<run-id>/task-board.proposed.json`

Parse is read-only for runtime state.

## Diff

Diff compares the proposed task board with:

- `task-board.json`
- `branch-state.json`
- `run-ledger.json`
- `worktree-map.json`
- `merge-queue.json`
- `resource-locks.json` when present

Output:

- `task-board.diff.json`
- `task-board.diff.md`

The diff lists retained, abandoned, redo-needed, paused, and needs-user-decision branches; invalid transitions; merge queue impact; worktree impact; resource-lock impact; parent aggregation impact; and stale plan warnings.

## Apply

Apply may directly perform only safe transitions such as planned to abandoned/paused, active to paused/redo-needed/retained, blocked to needs-user-decision, done to retained, and needs-review to redo-needed.

Unsafe transitions require GPT branch-manager or user confirmation, including reactivating abandoned/retained branches, high-risk downgrades, deleting merge queue entries, deleting resource locks, deleting worktrees, and turning root/parent aggregation nodes into execution nodes.

Apply writes:

- `task-board.json`
- `run-ledger.json`
- `branch-state.json`
- `worktree-map.json`
- `merge-queue.json`
- `artifact-graph.json`
- `redirect-plan.json`
- `events/task-board-apply-<timestamp>.json`

After apply, `/agent-run` must run `resume-safety-check.py` before continuing execution.
