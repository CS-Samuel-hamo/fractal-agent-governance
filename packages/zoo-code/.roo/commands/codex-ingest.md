---
description: Collect Codex CLI worker output back into Zoo artifacts.
argument-hint: <run-id> <task-id> <task-dir> <worktree>
mode: agent-executor
---

Collect Codex result for `$ARGUMENTS`.

Run `scripts/collect-codex-result.py`, verify scope guard output, and write `result.json` and `result.md`. Return the result to Zoo review and merge queue. Do not merge.
