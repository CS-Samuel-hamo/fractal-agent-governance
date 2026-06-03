# Executor Codex Worker Bridge

Executor absorbs the former Codex worker bridge capability.

When using Codex CLI, Executor must:

- confirm run_id, task_id, objective, allowed_files, denied_files, acceptance criteria, and test commands
- generate Task Packs only under `.zoo-agent/runs/**/codex-tasks/**`
- invoke Codex with `codex exec --cd <worktree> --sandbox workspace-write`
- set CODEX_HOME from the configured environment or explicit `--codex-home`
- run or prepare scope guard before completion
- collect `result.json`, `result.md`, and `codex-final-message.md` when available

Executor must not perform final review, integration, merge, push, global configuration writes, broad architecture decisions, or direct edits outside the assigned bounded task scope.

Do not use danger-full-access or sandbox bypass unless the user explicitly approves an isolated temporary test repository.
