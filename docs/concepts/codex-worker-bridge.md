# Codex Worker Bridge

The Codex worker bridge lets the governance runtime delegate bounded leaf tasks to Codex CLI.

The bridge generates a task pack, runs Codex in a scoped workspace or worktree, checks the changed files against allowed and denied paths, and collects the result as governance evidence.

Core flow:

1. Generate `.zoo-agent/runs/<run-id>/codex-tasks/<task-id>/`.
2. Run Codex with `codex exec --cd <worktree> --sandbox workspace-write`.
3. Run the scope guard.
4. Collect `.zoo-agent/runs/<run-id>/codex-results/<task-id>/`.
5. Let Zoo/GPT perform review, parent aggregation, and integration decisions.

Codex worker output is not final authority. It must not perform final review, integration, merge, push, or global configuration writes.
