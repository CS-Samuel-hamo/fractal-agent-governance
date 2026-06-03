---
description: Run a generated Codex Task Pack through Codex CLI.
argument-hint: <task-dir> <worktree>
mode: agent-executor
---

Run Codex CLI for `$ARGUMENTS`.

Use:

```bash
python scripts/run-codex-worker.py --task-dir <task-dir> --workspace <worktree> --sandbox workspace-write --codex-home D:\AI_DEV\codex_home --timeout-seconds 360
```

Codex Worker is code-only by default. After it exits, run the external harness checks: targeted tests, scope guard, and result collection.

Do not use danger bypass. Do not commit, push, merge, or delete branches.
