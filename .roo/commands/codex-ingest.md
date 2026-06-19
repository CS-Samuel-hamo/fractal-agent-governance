# Codex Ingest

Collect and summarize Codex worker results.

## Collect One Task

```powershell
$collect = if (Test-Path ".\scripts\collect_codex_result.py") { ".\scripts\collect_codex_result.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\collect_codex_result.py" }
python $collect `
  --run-id "<run-id>" `
  --task-id "<task-id>" `
  --task-dir "<task-dir>" `
  --workspace "<workspace>"
```

## Summarize A Run

```powershell
$summary = if (Test-Path ".\scripts\summarize_ai_native_run.py") { ".\scripts\summarize_ai_native_run.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\summarize_ai_native_run.py" }
python $summary `
  --run-id "<run-id>" `
  --workspace "<workspace>"
```

Inspect `ai-native-summary.json` and `ai-native-summary.md` before merge decisions.

