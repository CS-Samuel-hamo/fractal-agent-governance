# Codex CLI as Execution Worker

Codex CLI performs bounded implementation only after Zoo has selected it and generated a Task Pack.

Default command shape:

```bash
codex exec --cd <worktree> --sandbox workspace-write --output-last-message <result-file> -
```

The prompt is passed through stdin from `CODEX_TASK_PROMPT.md`.

Do not use `--dangerously-bypass-approvals-and-sandbox` except in a one-time isolated temporary test repository and only with explicit user approval.

Codex CLI must:

- read `AGENTS.md`, `TASKS.yaml`, `ACCEPTANCE.md`, and `CODEX_TASK_PROMPT.md`
- execute only the requested `task_id`
- stay within `allowed_files`
- avoid `denied_files`
- run relevant tests when available
- run `python check_codex_scope.py <task_id>`
- update `PROGRESS.md` or `BLOCKERS.md`
- return evidence

Zoo collects Codex output into `result.json` and `result.md`, then runs scope guard, quality gate, and review gate.
