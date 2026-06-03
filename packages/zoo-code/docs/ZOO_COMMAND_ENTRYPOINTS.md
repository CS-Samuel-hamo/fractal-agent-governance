# Zoo Command Entrypoints

This template exposes the AI-native execution loop through Roo/Zoo command files.

## Default Command

Use `.roo/commands/agent-run.md` for normal engineering work.

It routes to:

```text
<workspace>/scripts/run_ai_native_task.py
or $env:USERPROFILE\.roo\agent-governance-kit\scripts\run_ai_native_task.py
```

Use the workspace dispatcher when present. Use the installed global governance kit dispatcher when an old business project has no local bridge scripts.

## Bootstrap Command

Use `.roo/commands/agent-setup.md` as the one-touch setup command for new and existing projects. It updates global `.roo`, the installed `agent-governance-kit`, and the target project in one operation.

Recommended flow:

1. Open the project.
2. Run `agent-setup`.
3. Review `.zoo-agent/one-touch-setup-report.md`, `.zoo-agent/agent-bootstrap-report.md`, and `.zoo-agent/bootstrap-report.md`.
4. Reload the project after bootstrap.
5. Run `agent-run` for the actual task.
6. Run closure scripts (`check_task_board_consistency.py`,
   `run_quality_gate.py`, and when authorized `process_merge_queue.py`) before
   claiming merge readiness.

Direct PowerShell equivalent:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\setup_zoo_agent.py `
  --project "<project>" `
  --mode auto
```

Setup is explicit rather than automatic on reload because it writes global and project governance artifacts. This keeps local project customizations visible, backed up, and reversible.

Use `.roo/commands/agent-bootstrap.md` only when the global kit is already current and you only need to refresh or repair the current project.

Inactive proposals should live under `.zoo-agent/bootstrap/proposals/`, not beside active `.roo/rules/*.md` files. Files in the proposal inbox do not affect agent behavior until reviewed and applied.

## Local Project Overrides

If a business project has its own `.roo/commands` or `.roo/rules`, those files may shadow global Roo/Zoo entrypoints.

Patch that project with:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\sync_zoo_entrypoints.py `
  --project-root "<business-project>" `
  --project-only `
  --backup-root "<business-project>\.roo-backups\ai-native-bootstrap"
```

The project patch:

- injects the AI-native dispatcher override into local `.roo/commands/agent-run.md`
- injects the AI-native progress summary override into local `.roo/commands/progress.md`
- adds `.roo/rules/00-ai-native-global-bridge.md`
- copies missing lower-level Codex commands and skills
- preserves existing local command/rule text with backups

Level behavior:

- Level 0/1: optimistic isolated execution by default.
- Level 2: planned isolated execution when `--execute-planned` is authorized.
- Level 3: parent workstream artifact plus generated leaf skeletons.
- Level 4: human gate.

Context behavior:

- Do not first classify the request as short-term or long-term.
- Treat the user input as the current task.
- Let the resolved dispatcher attach project charter, active goal, and task board context through `.zoo-agent/runs/<run-id>/task-contexts/<task-id>.json`.
- Durable project state is read-only unless an explicit durable update is requested and `--allow-durable-state-update` is passed.

Execution graph behavior:

- `executor-selection.json` includes `execution_graph`.
- Use `chain_weight` and `judgment_node_count` to understand how heavy the selected chain is.
- Use `parallel_contract.conflict_keys` to decide whether tasks can run concurrently.
- Use `rollback_contract.mode` to understand how failed work can be discarded or gated.
- Use `quality-gate.json` and `merge-queue-processing.json` to decide whether
  evidence has moved from record-only to serial integration ready.

## Lower-Level Commands

- `.roo/commands/codex-task.md`: generate a task pack.
- `.roo/commands/codex-run.md`: run an existing task pack.
- `.roo/commands/codex-ingest.md`: collect or summarize results.
- `.roo/commands/codex-review.md`: review result evidence.
- `.roo/commands/progress.md`: refresh run progress.

These are diagnostic and manual-control commands. They should not replace
`agent-run.md` as the default path.
