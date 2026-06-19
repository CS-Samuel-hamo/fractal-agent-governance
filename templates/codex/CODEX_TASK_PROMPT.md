Read `AGENTS.md`, `TASKS.yaml`, and `ACCEPTANCE.md` first.
If present, read `TASK_CONTEXT.md` or `TASK_CONTEXT.json` as read-only durable background.

Execute only task_id=`{{TASK_ID}}`.

Objective:
{{OBJECTIVE}}

Hard constraints:
0. Treat the Objective below as the current task request, not as a replacement for the project charter or root goal. Do not classify it as short-term or long-term before acting.
1. Only modify files allowed by `TASKS.yaml` for task_id=`{{TASK_ID}}`.
2. If you need to touch a denied file or a file outside `allowed_files`, stop and explain why.
3. Do not infer broader architecture changes.
4. Do not add dependencies unless explicitly approved.
5. Do not change database schema, auth/security, public API, or deployment config unless explicitly approved.
6. Start with `git status`.
7. Finish with `git diff --name-only` and list the relevant test command(s) the harness should run.
8. Do not run pytest or `check_codex_scope.py` inside Codex unless explicitly required by the runtime note; the external harness runs tests, scope guard, and result collection after Codex exits.
9. Update `PROGRESS.md` with what changed and mark tests/scope as `harness pending` if you did not run them.
10. If blocked, update `BLOCKERS.md` instead of guessing.
11. Do not commit, push, merge, reset, or delete branches.
12. Do not modify project charter, goal contracts, project profile, or project map unless `TASK_CONTEXT` write_policy explicitly allows it and the task scope allows those files.

Return a concise final report with:
- Files changed
- Tests/checks run or deferred to harness
- Scope guard result or `harness pending`
- Remaining risks or blockers
