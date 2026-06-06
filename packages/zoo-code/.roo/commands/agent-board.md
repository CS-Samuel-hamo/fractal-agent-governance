---
description: Render the integrated Zoo Governance Board for the active project/run.
argument-hint: <optional run id>
mode: agent-orchestrator
---

Generate a read-only integrated governance board. Do not modify business code.

The board keeps durable state and runtime state in their original files, then
renders one human-facing view:

- `.zoo-agent/BOARD.md`
- `.zoo-agent/status-board.json`
- `.zoo-agent/runs/<run-id>/BOARD.md`
- `.zoo-agent/runs/<run-id>/status-board.json`

Recommended command:

```powershell
$board = if (Test-Path ".\scripts\render_governance_board.py") { ".\scripts\render_governance_board.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\render_governance_board.py" }
python $board `
  --workspace "<workspace>" `
  --run-id "<run-id>"
```

If no run id is provided, resolve it from `.zoo-agent/current-run.json` or the
latest `.zoo-agent/runs/<run-id>` directory.

Use this board as the daily management surface. Edit task intent in
`.zoo-agent/TASKS.md` or `.zoo-agent/runs/<run-id>/TASKS.md`, then apply the
task board; do not hand-edit `status-board.json`.
