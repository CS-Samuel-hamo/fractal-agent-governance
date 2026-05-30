# Version, Worktree, and Merge Gates

## Worktree Usage
Use a dedicated Git worktree for each non-trivial branch/task when parallelism or isolation is useful.
Branch naming convention:
- `agent/<branch-id>/<short-purpose>` for agent-managed work
- `review/<task-id>` for review-only branches if needed
- `integration/<release-or-parent-id>` for integration branches

## Checkpoint Discipline
Keep Zoo Code checkpoints enabled. Treat checkpoints as short-horizon safety snapshots, not as a replacement for Git commits.

## Commit Discipline
Recommended commit sequence:
1. `plan: add task contract for <task-id>`
2. `feat|fix|refactor: implement <task-id>`
3. `test: cover <task-id>`
4. `docs: update branch state for <task-id>`
5. `review: record verdict for <task-id>`
6. `governance: record postmortem/evolution <event-id>` if a failure occurred

## Merge Gate
A task cannot be merged unless implementation contract exists, executor evidence exists, reviewer verdict is positive, required checks passed or were explicitly waived, and branch-state is updated.

## Rollback
Every integration summary must include merge commit/branch ref, revert command or checkpoint restoration note, and affected feature flags/config keys if any.
