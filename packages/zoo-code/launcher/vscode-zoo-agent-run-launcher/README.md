# Zoo Agent Run Launcher

A small local VS Code helper extension for the Zoo Code Agent Governance Kit.

Behavior:

- Shows a status bar item: `Agent`.
- Provides Command Palette actions for progress, task-board apply, resume safety, redirect, resume, and best-effort Stop Then Snapshot.
- Adds an Explorer Tree View: `Agent Progress`.
- Reads `.zoo-agent/runs/**/progress.json` and related governance artifacts.
- Exports a human-editable `.zoo-agent/runs/<run-id>/TASKS.md` task board plus per-branch `tasks/*.md` files.
- Applies user edits from the task board back into branch state, redirect plan, run ledger, artifact graph, and merge queue artifacts.
- Opens merge queue, resource locks, parallel report, and resume-safety-check artifacts.
- Does not edit business code, merge branches, delete worktrees, or read secrets.

Stop Then Snapshot is best effort. If no credible Zoo/Roo stop command is discoverable through VS Code command APIs, the extension asks the user to click the native Zoo Code Stop button and then run Agent: Show Progress.

Use `Agent: Open Task Board` after a progress snapshot to review the root task and folded child tasks in plain Markdown. Edit `user_override` fields such as `retained`, `abandoned`, `redo_needed`, `paused`, or `needs_user_decision`, then run `Agent: Apply Task Board` before resuming the agent.

Settings are under `zooAgentLauncher.*`.
