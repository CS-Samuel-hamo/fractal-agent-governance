---
description: Generate a bounded Codex Task Pack for the current Zoo run.
argument-hint: <run-id> <task-id> <objective>
mode: agent-executor
---

Generate a Codex Task Pack for `$ARGUMENTS`.

Required behavior:

1. Confirm run id, task id, objective, allowed files, denied files, acceptance, and test commands.
2. Run `scripts/generate-codex-task-pack.py`.
3. Write under `.zoo-agent/runs/<run-id>/codex-tasks/<task-id>/`.
4. Do not execute Codex CLI unless separately requested.
5. Do not modify product code.
