# State Source Hierarchy

This hierarchy prevents stale plans and conflicting runtime facts.

1. `TASKS.md`
   - Human-editable control surface.
   - May express user intent, priority, branch status overrides, retained/abandoned/redo instructions.
   - Not a runtime fact source until Apply Task Board compiles it.

2. `task-board.json`
   - Machine projection produced by Apply Task Board.
   - Not the final runtime fact source.
   - Must not be treated as newer user intent when `TASKS.md` is newer.

3. `run-ledger.json`
   - Process fact source.
   - Owns `current_state`, `previous_state`, `next_allowed_states`, pause/redirect/resume gate state.

4. `branch-state.json`
   - Fractal branch fact source.
   - Owns branch id, parent id, branch status, owned resources, exit condition, evidence.

5. `artifact-graph.json`
   - Evidence, gate, review, diagnostics, aggregation version fact source.
   - Reviewers and integrators must not rely on untracked artifacts.

6. `worktree-map.json`
   - Git branch, worktree path, and branch id mapping fact source.

7. `resource-locks.json`
   - Path and semantic resource ownership fact source.
   - Enhances `path-locks.json` with API, DTO/schema, Proc/data-source, event, queue, flag, fixture, and config resources.

8. `merge-queue.json`
   - Integration order fact source.
   - Parallel branches cannot merge directly.

## One-Way Apply

```text
TASKS.md
  -> parse
  -> task-board.proposed.json
  -> diff
  -> validate
  -> apply
  -> patch run-ledger / branch-state / worktree-map / merge-queue / artifact-graph
```

No runtime file may silently overwrite a user-edited `TASKS.md`. If sources conflict, move to `needs_user_decision` or GPT branch-manager decision instead of guessing.

## No Stale Plan

- If `TASKS.md` is newer than `task-board.json` or `redirect-plan.json`, run Apply Task Board first.
- If `redirect-plan.json` is newer than `branch-state.json`, apply redirect or run resume safety before continuing.
- If `merge-queue.json` references abandoned, redo-needed, or paused branches, integration must fail until the queue is updated.
