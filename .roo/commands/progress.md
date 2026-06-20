# Progress

Show AI-native run progress from the run summary.

```powershell
$summary = if (Test-Path ".\scripts\summarize_ai_native_run.py") { ".\scripts\summarize_ai_native_run.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\summarize_ai_native_run.py" }
python $summary `
  --run-id "<run-id>" `
  --workspace "<workspace>"
```

Use the summary status counts to decide whether the next action is retry, leaf decomposition, review, or merge-candidate handling.

For closure-sensitive decisions, also inspect:

- `.zoo-agent/runs/<run-id>/task-board-consistency.json`
- `.zoo-agent/runs/<run-id>/risk-register.json`
- `.zoo-agent/runs/<run-id>/quality-gate.json`
- `.zoo-agent/runs/<run-id>/merge-queue-processing.json`
- `.zoo-agent/locks/resource-locks.json`

