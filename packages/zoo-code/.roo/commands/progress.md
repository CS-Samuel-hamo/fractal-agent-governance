---
description: Generate a read-only progress snapshot for the current Zoo Agent run.
argument-hint: <optional run id>
mode: agent-orchestrator
---

Generate a read-only Progress Snapshot for the current Zoo Agent run.

Arguments:

`$ARGUMENTS`

Rules:

- Do not modify business code.
- Do not read secrets, API keys, tokens, provider profiles, or `.env` contents.
- Read only governance runtime artifacts under `.zoo-agent`.
- Generate or refresh:
  - `.zoo-agent/runs/<run-id>/progress.json`
  - `.zoo-agent/runs/<run-id>/progress.md`
  - `.zoo-agent/runs/<run-id>/progress-tree.md`
  - `.zoo-agent/current-run.json`
  - `.zoo-agent/TASKS.md`
  - `.zoo-agent/runs/<run-id>/TASKS.md`
  - `.zoo-agent/runs/<run-id>/task-board.json`
  - `.zoo-agent/runs/<run-id>/tasks/<branch>.md`
- Treat `.zoo-agent/TASKS.md` as the project-level task board entry for the current run.
- Treat `.zoo-agent/runs/<run-id>/TASKS.md` as the current run's task board archive.
- If either task board is newer than `task-board.json`, preserve user edits and report that Apply Task Board is required.
- Include goal contract, run-ledger, artifact-graph, branch-state, worktree-map, merge-queue, quality gate, obligation ledger, review reports, metrics, checkpoints when recorded, and git status/diff stat when available.
- Show root -> parent -> active child context.
- Keep non-active siblings and done branches collapsed by default in `progress.json`.

Recommended commands:

```bash
python scripts/generate-progress-snapshot.py --run-id <run-id>
python scripts/render-progress-tree.py --run-id <run-id>
python scripts/export-task-board.py --run-id <run-id>
python scripts/check-task-board-consistency.py --run-id <run-id>
```
