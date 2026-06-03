---
description: Create a non-coding redirect plan from the latest progress snapshot.
argument-hint: <new direction>
mode: agent-orchestrator
---

Create a non-coding Redirect Plan for the current Zoo Agent run.

New direction:

`$ARGUMENTS`

Rules:

- Base the plan on the latest `progress.json`.
- Prefer user-edited `TASKS.md` when present.
- Update `TASKS.md` Current User Intent when present.
- Do not modify business code.
- Do not merge.
- Do not delete worktrees.
- Do not read secrets, API keys, tokens, provider profiles, or `.env` contents.
- Generate:
  - `.zoo-agent/runs/<run-id>/redirect-plan.json`
  - `.zoo-agent/runs/<run-id>/redirect-plan.md`
  - `.zoo-agent/runs/<run-id>/events/redirect-<timestamp>.json`
- Update only governance runtime state:
  - `run-ledger.current_state = replanning`
  - branch status: `retained`, `abandoned`, `redo_needed`, or `needs_user_decision`
  - worktree status: `retained`, `paused`, or `abandoned`
  - merge queue impact: `unchanged`, `reorder_required`, or `clear_required`
- Resume execution only through `/agent-run`.
- Resume execution must pass `scripts/resume-safety-check.py` first.

Recommended command:

```bash
python scripts/apply-redirect-plan.py --run-id <run-id> --direction "<new direction>"

# Or, when TASKS.md was edited:
python scripts/apply-task-board.py --run-id <run-id>
python scripts/resume-safety-check.py --run-id <run-id>
```
