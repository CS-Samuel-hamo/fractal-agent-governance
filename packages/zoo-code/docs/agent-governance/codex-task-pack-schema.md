# Codex Task Pack Schema

Task Pack output directory:

`.zoo-agent/runs/<run-id>/codex-tasks/<task-id>/`

Required files:

- `AGENTS.md`
- `TASKS.yaml`
- `ACCEPTANCE.md`
- `CODEX_TASK_PROMPT.md`
- `PROGRESS.md`
- `BLOCKERS.md`
- `check_codex_scope.py`
- `task-metadata.json`

`TASKS.yaml` must define:

- `id`
- `status`
- `objective`
- `branch_id`
- `allowed_files`
- `denied_files`
- `requires_approval_if`
- `acceptance`
- `test_commands`
- `evidence_required`

`AGENTS.md` must stay short and contain hard rules only. `CODEX_TASK_PROMPT.md` must be directly usable as stdin for `codex exec`.
