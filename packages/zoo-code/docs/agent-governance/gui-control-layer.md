# GUI Control Layer

The GUI control layer is a discoverable entry point over the existing slash commands. It does not replace `/agent-run`, `/progress`, or `/redirect`.

## Control Mapping

- Zoo Stop button:
  - Stops or interrupts the current Zoo Code task execution.
  - Does not generate a full progress snapshot.
  - Does not mean the project failed.

- Agent: Show Progress:
  - Maps to `/progress`.
  - Generates `progress.json`, `progress.md`, and `progress-tree.md`.
  - Refreshes the Agent Progress Tree.

- Agent: Redirect Current Run:
  - Maps to `/redirect`.
  - Changes control objective, direction, or branch strategy from current progress.
  - Does not enter coding directly.

- Agent: Copy Resume Command:
  - Maps to `/agent-run continue run <run-id>`.
  - Lets execution resume through the orchestrator.

- Agent Progress Tree:
  - Reads `progress.json`.
  - Shows root -> parent -> active child context.
  - Keeps useful artifacts, evidence, branches, and worktrees visible.

- Agent Task Board:
  - Opens `TASKS.md`.
  - `TASKS.md` is the recommended human-editable control file.
  - Applying it synchronizes `branch-state.json`, `redirect-plan.json`, `run-ledger.json`, `worktree-map.json`, and `merge-queue.json`.

- Agent: Run Resume Safety Check:
  - Runs `resume-safety-check.py`.
  - Opens `resume-safety-check.md`.
  - Blocks resume when stale plans, unsafe queue entries, missing aggregation, or resource-lock conflicts exist.

- Artifact openers:
  - Open Merge Queue.
  - Open Resource Locks.
  - Open Parallel Report.

## Recommended User Flow

1. Long task, uncertain direction:
   - Click the native Zoo Code Stop button.
   - Click the Agent status bar item.
   - Choose Show Progress Snapshot.
   - Inspect Agent Progress Tree.

2. Goal, classification, or decomposition is wrong:
   - Choose Redirect Current Run.
   - Enter the new direction.
   - Review Redirect Plan.
   - Copy or start the Resume Command.

3. Do not continue:
   - Use redirect direction such as `abort/archive`.
   - Worktrees are not deleted automatically.
   - Merge is not executed automatically.

## Design Principles

- Stop is a steering mechanism, not a failure state.
- Human intervention redirects the control objective, not every subtask manually.
- Useful artifacts, evidence, branches, and worktrees should be retained.
- Only necessary branches are marked `redo_needed`, `abandoned`, or `retained`.
- Low-risk work stays lightweight; high-risk work keeps stronger gates.
- This is a lightweight VS Code Tree View, not a heavy dashboard.
- `TASKS.md` is the preferred human editing surface. Runtime JSON files are machine state and should not be edited by hand.

## Task Board Files

Long fractal runs use a small index plus per-branch task documents:

```text
.zoo-agent/runs/<run-id>/
  TASKS.md
  task-board.json
  tasks/
    root.md
    <parent-branch>.md
    <child-branch>.md
```

`TASKS.md` shows Current User Intent, the current active path, user control values, and a compact tree. `tasks/<branch>.md` stores branch-local objective, owned paths, shared paths, provides/consumes, acceptance criteria, verification plan, evidence, and user override.

## Fallback Behavior

`Agent: Stop Then Snapshot` uses `vscode.commands.getCommands(true)` to look for credible Zoo/Roo stop or cancel commands. If none is found, it does not guess or hard-code unknown internal command ids. It asks the user to click the native Zoo Code Stop button, then run Agent: Show Progress Snapshot.
