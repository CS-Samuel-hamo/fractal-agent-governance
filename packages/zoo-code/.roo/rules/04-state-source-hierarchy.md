# State Source Hierarchy

`TASKS.md` is human-editable intent, `task-board.json` is compiled projection, `run-ledger.json` is process fact source, `branch-state.json` is branch fact source, `artifact-graph.json` is evidence/gate version fact source, `worktree-map.json` is git/worktree mapping fact source, `resource-locks.json` is path plus semantic ownership fact source, and `merge-queue.json` is integration order fact source.

Apply is one-way: `TASKS.md -> parse -> task-board.proposed.json -> diff -> validate -> apply -> runtime facts`.

If `TASKS.md` is newer than `task-board.json` or `redirect-plan.json`, `/agent-run` must require Apply Task Board before continuing. If facts conflict, move to `needs_user_decision` or GPT branch-manager decision instead of guessing.
