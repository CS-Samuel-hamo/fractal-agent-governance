---
name: codex-result-ingestion
description: Collect, summarize, and review Codex worker and AI-native dispatcher execution results.
version: 3.9.1
scope: global
applies_to: agent-codex-worker
last_updated: 2026-06-03
deprecated_by: ""
---

# Codex Result Ingestion

Use this skill when collecting or summarizing Codex worker results.

Collect one task:

```powershell
$collect = if (Test-Path ".\scripts\collect_codex_result.py") { ".\scripts\collect_codex_result.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\collect_codex_result.py" }
python $collect `
  --run-id "<run-id>" `
  --task-id "<task-id>" `
  --task-dir "<task-dir>" `
  --workspace "<workspace>"
```

Summarize the run:

```powershell
$summary = if (Test-Path ".\scripts\summarize_ai_native_run.py") { ".\scripts\summarize_ai_native_run.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\summarize_ai_native_run.py" }
python $summary `
  --run-id "<run-id>" `
  --workspace "<workspace>"
```

