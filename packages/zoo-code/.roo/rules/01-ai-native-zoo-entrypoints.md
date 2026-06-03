# AI-Native Zoo Entrypoints

- Use `.roo/commands/agent-run.md` as the default command for bounded engineering work.
- Do not first classify the user request as short-term or long-term. Pass it as the current task and let the dispatcher attach durable project context as background.
- The dispatcher must write `.zoo-agent/runs/<run-id>/task-contexts/<task-id>.json` and `.md` before routing or task-pack generation.
- The dispatcher must include `execution_graph` in `executor-selection.json` so routing weight, judgment nodes, conflict keys, parallel contract, and rollback contract are inspectable.
- Project charter, goal contract, project profile, and project map are read-only unless the user explicitly requests a durable update and `--allow-durable-state-update` is passed.
- Resolve the dispatcher from `<workspace>/scripts/run_ai_native_task.py` first, then `$env:USERPROFILE\.roo\agent-governance-kit\scripts\run_ai_native_task.py`.
- Level 0/1 should default to the resolved dispatcher, not direct task-pack generation.
- Level 2 can call Codex through `--execute-planned`, but execution must remain isolated in a managed worktree.
- Level 3 parent tasks must produce a fractal workstream and leaf skeletons; do not execute the parent as one broad Codex run.
- Level 3 leaf skeletons should be re-routed through the resolved dispatcher, usually as Level 0/1, after any needed refinement.
- Level 4 requires a human gate before worker execution.
- Treat `.zoo-agent/runs/<run-id>/ai-native-summary.json` as the run-level status source.
- Before claiming completion or merge readiness, refresh task-board consistency,
  risk register, quality gate, and merge queue processing evidence when
  applicable.
