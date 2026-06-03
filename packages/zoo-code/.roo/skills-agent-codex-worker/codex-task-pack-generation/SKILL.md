---
name: codex-task-pack-generation
description: Generate bounded Codex Task Packs or route through the AI-native dispatcher for Codex worker execution.
version: 3.9.1
scope: global
applies_to: agent-codex-worker
last_updated: 2026-06-03
deprecated_by: ""
---

# Codex Task Pack Generation

Use this skill when creating a Codex Task Pack for a bounded worker task.

Default path:

```powershell
$dispatcher = if (Test-Path ".\scripts\run_ai_native_task.py") { ".\scripts\run_ai_native_task.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\run_ai_native_task.py" }
python $dispatcher ...
```

Direct task-pack generation:

```powershell
$taskpack = if (Test-Path ".\scripts\generate_codex_task_pack.py") { ".\scripts\generate_codex_task_pack.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\generate_codex_task_pack.py" }
python $taskpack `
  --run-id "<run-id>" `
  --task-id "<task-id>" `
  --objective "<objective>" `
  --allowed-file "src/**" `
  --allowed-file "tests/**"
```

Use fast prompt only when the dispatcher or planner selects fast-path execution.
