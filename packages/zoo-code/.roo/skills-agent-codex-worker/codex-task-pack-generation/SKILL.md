---
name: codex-task-pack-generation
description: Generate bounded Codex CLI Task Packs from Zoo run, branch, and task contracts.
version: 0.3.9
scope: governance
applies_to: agent-executor
last_updated: 2026-06-01
deprecated_by:
---

# Codex Task Pack Generation

Use this skill when Zoo needs a bounded Codex CLI worker task.

Steps:

1. Confirm run id, task id, branch id, objective, allowed files, denied files, acceptance, and tests.
2. Generate `.zoo-agent/runs/<run-id>/codex-tasks/<task-id>/`.
3. Include `AGENTS.md`, `TASKS.yaml`, `ACCEPTANCE.md`, `CODEX_TASK_PROMPT.md`, `PROGRESS.md`, `BLOCKERS.md`, `check_codex_scope.py`, and `task-metadata.json`.
4. Do not execute Codex CLI unless the user or automation policy requested execution.
