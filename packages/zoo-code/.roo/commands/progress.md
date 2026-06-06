---
description: Generate a read-only progress snapshot for the current Zoo Agent run.
argument-hint: <optional run id>
mode: agent-orchestrator
---

<!-- BEGIN AI_NATIVE_PROGRESS_SUMMARY -->
## AI-Native Run Summary

For AI-native dispatcher runs, refresh progress with:

```powershell
$summary = if (Test-Path ".\scripts\summarize_ai_native_run.py") { ".\scripts\summarize_ai_native_run.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\summarize_ai_native_run.py" }
python $summary `
  --run-id "<run-id>" `
  --workspace "<workspace>"
```

For the integrated management board, refresh:

```powershell
$board = if (Test-Path ".\scripts\render_governance_board.py") { ".\scripts\render_governance_board.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\render_governance_board.py" }
python $board `
  --run-id "<run-id>" `
  --workspace "<workspace>"
```

Read `.zoo-agent/BOARD.md` first for day-to-day status and task management.

Read `.zoo-agent/runs/<run-id>/ai-native-summary.json` before retry, decomposition, review, or merge-candidate decisions.

For closure-sensitive decisions, also inspect:

- `.zoo-agent/runs/<run-id>/task-board-consistency.json`
- `.zoo-agent/runs/<run-id>/risk-register.json`
- `.zoo-agent/runs/<run-id>/quality-gate.json`
- `.zoo-agent/runs/<run-id>/merge-queue-processing.json`
- `.zoo-agent/locks/resource-locks.json`
<!-- END AI_NATIVE_PROGRESS_SUMMARY -->
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
