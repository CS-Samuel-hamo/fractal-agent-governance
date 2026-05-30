# Worktree Branch Lifecycle

1. planned: branch contract exists, worktree not created.
2. created: worktree path exists, branch mapped.
3. active: executor is working inside isolated worktree.
4. review: completion evidence and quality artifacts exist.
5. queued: branch passed gate/review/path-lock checks and entered merge queue.
6. merged: GPT integrator completed serial merge decision.
7. abandoned: branch will not merge.
8. archived: evidence and rollback/checkpoint references are retained.

Cleanup is allowed only when:

- branch is committed or archived
- evidence is recorded
- merge queue status is resolved
- rollback checkpoint is available or explicitly unavailable

Cleanup scripts must default to dry-run and must not delete worktrees unless explicit execution flags are passed.
