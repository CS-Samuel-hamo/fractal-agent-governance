# Agent Rules

- Start every task with `git status`.
- Work only within the assigned task scope.
- Do not modify files outside `allowed_files` in `TASKS.yaml`.
- Do not modify `denied_files` in `TASKS.yaml`.
- Do not change architecture unless the task explicitly asks for it.
- Do not add dependencies unless explicitly approved.
- Do not change database schema unless explicitly approved.
- Do not change auth, security, public API, or deployment config unless explicitly approved.
- Do not run `git push`.
- Do not run `git reset --hard`.
- Do not delete files unless explicitly instructed.
- If the task is ambiguous, stop and ask up to 5 clarifying questions before coding.
- Before completion, run `git diff --name-only` and list the relevant test command(s) for the harness.
- Do not run pytest or `check_codex_scope.py` inside Codex unless the runtime note explicitly requires it; the external harness runs tests, scope guard, and result collection after Codex exits.
- Update `PROGRESS.md` and `BLOCKERS.md` when relevant.
- Summarize final changes with evidence.
