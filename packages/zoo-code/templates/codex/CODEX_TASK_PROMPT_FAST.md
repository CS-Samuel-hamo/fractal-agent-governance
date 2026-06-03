Execute only task_id=`{{TASK_ID}}`.
If present, read `TASK_CONTEXT.md` or `TASK_CONTEXT.json` as read-only durable background.

Objective:
{{OBJECTIVE}}

Fast path contract:
0. Treat the Objective as the current task request, not as a replacement for the project charter or root goal. Do not classify it as short-term or long-term before acting.
1. Start with `git status --short`.
2. Modify only files allowed by `TASKS.yaml` for task_id=`{{TASK_ID}}`.
3. Do not touch denied files.
4. Prefer the smallest working change that satisfies the objective.
5. If the fix requires files outside scope, an architecture change, a dependency change, a schema/config/auth/security/API change, stop and explain the blocker.
6. Do not commit, push, merge, reset, or delete branches.
7. Finish with `git diff --name-only`.
8. Do not modify project charter, goal contracts, project profile, or project map unless `TASK_CONTEXT` write_policy explicitly allows it and the task scope allows those files.

Return a concise final report with:
- Files changed
- Tests/checks you ran, or `harness pending`
- Blockers or risks
