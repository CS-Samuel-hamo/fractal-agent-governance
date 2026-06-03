# Task Board Control

`TASKS.md` is the human-editable control surface for long agent runs. Runtime JSON remains machine state; users should steer the run through the task board and then apply it back to the run artifacts.

## Files

```text
.zoo-agent/runs/<run-id>/
  TASKS.md
  task-board.json
  tasks/
    root.md
    <branch-id>.md
```

- `TASKS.md` is the compact global plan/task index.
- `task-board.json` is the structured projection used by schedulers and tools.
- `tasks/<branch-id>.md` is the branch-local plan with objective, ownership, contracts, verification, evidence, and user override.

## Long Task Splitting

Long runs should use hierarchical task documents instead of a single giant task file. This maps directly to fractal task governance:

- Level 0: root goal in `TASKS.md`.
- Level 1: major branches under `tasks/<branch>.md`.
- Level 2+: deeper branch documents only when `needs_decomposition` is recorded.

The branch manager decides whether to create deeper files using the same max depth, dependency, risk, and parent aggregation rules as normal fractal decomposition.

## User Intervention

When the user interrupts a run:

1. Generate progress and task board artifacts.
2. User edits `TASKS.md` or a branch document.
3. Parse and diff the task board.
4. Apply the task board if transitions are safe.
5. Run resume safety check.
6. Resume with `/agent-run continue run <run-id> using TASKS.md`.

Allowed user statuses:

- `active`
- `retained`
- `abandoned`
- `redo_needed`
- `paused`
- `blocked`
- `needs_user_decision`
- `done`

Applying the task board updates:

- `branch-state.json`
- `redirect-plan.json`
- `run-ledger.json`
- `artifact-graph.json`
- `worktree-map.json`
- `merge-queue.json`

It also writes `task-board.proposed.json`, `task-board.diff.json`, `task-board.diff.md`, `redirect-plan.json`, and a task-board apply event.

Completed work marked `retained` stays available for parent aggregation. Incorrect or obsolete work marked `redo_needed` blocks direct merge and forces replanning. Abandoned work is not deleted automatically.

## Parallel Scheduling

The scheduler may read `task-board.json` as branch input. Parallel execution is only allowed when branch ownership, shared paths, provides/consumes contracts, acceptance criteria, verification plan, risk level, worktree, path locks, and parent approval are all present and safe.

Branches changed by the task board affect scheduling:

- `retained`: no execution required; available for parent aggregation.
- `abandoned`: not schedulable and not mergeable.
- `redo_needed`: not schedulable until replanned.
- `paused`: not schedulable until resumed.

All parallel branches still enter a serial merge queue after completion.

## Safety

Task board control does not edit business code, merge branches, delete worktrees, read secrets, or rewrite history. It only changes governance artifacts that describe what should happen next.
