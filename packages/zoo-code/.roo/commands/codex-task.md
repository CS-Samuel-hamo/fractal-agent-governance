# Codex Task

Lower-level command for generating a Codex Task Pack.

Prefer `.roo/commands/agent-run.md` for normal Zoo work. Use this when the planner has already decided to prepare a governed task pack without executing it.

## Command Shape

```powershell
$taskpack = if (Test-Path ".\scripts\generate_codex_task_pack.py") { ".\scripts\generate_codex_task_pack.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\generate_codex_task_pack.py" }
python $taskpack `
  --run-id "<run-id>" `
  --task-id "<task-id>" `
  --objective "<objective>" `
  --allowed-file "src/**" `
  --allowed-file "tests/**" `
  --test-command "python -m pytest tests"
```

Use `--prompt-template CODEX_TASK_PROMPT_FAST.md` only for fast-path execution. Planned and governed paths should use the default full prompt.
