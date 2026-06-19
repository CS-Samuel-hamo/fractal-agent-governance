# Codex Task Pack Rule

Codex workers must execute only within the assigned task scope.

- Fast path uses `CODEX_TASK_PROMPT_FAST.md`.
- Planned/governed path uses `CODEX_TASK_PROMPT.md`.
- Codex CLI is the execution backend only; it is not the planner or
  orchestrator.
- The runner provides `TASKS.yaml`, `AGENTS.md`, `ACCEPTANCE.md`, `PROGRESS.md`, and `BLOCKERS.md`.
- `TASKS.yaml` and `task-metadata.json` must include the bound `goal_id`.
- When present, the runner also provides `TASK_CONTEXT.json` and `TASK_CONTEXT.md`; treat them as durable background and follow their write policy.
- Workers do not commit, push, merge, reset, or delete branches.
- Scope guard and tests are owned by the external harness unless the runtime note explicitly requires otherwise.

