# Codex Run

Lower-level command for running an already generated Codex Task Pack.

Prefer `.roo/commands/agent-run.md` for normal Zoo work. Use this only when a task pack already exists or when debugging the worker bridge.

## Required Inputs

- `task_dir`
- `workspace`

## Command Shape

```powershell
$worker = if (Test-Path ".\scripts\run_codex_worker.py") { ".\scripts\run_codex_worker.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\run_codex_worker.py" }
python $worker `
  --task-dir "<task-dir>" `
  --workspace "<workspace>" `
  --sandbox workspace-write `
  --codex-home "D:\AI_DEV\codex_home" `
  --timeout-seconds 360
```

The external harness owns tests, scope guard, and result collection unless a runtime note explicitly requires otherwise.
