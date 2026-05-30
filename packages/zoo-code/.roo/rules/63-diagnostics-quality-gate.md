# Diagnostics Quality Gate

Diagnostics are quality-gate input.

- collect before/after diagnostics when available
- new Error diagnostics block integration unless GPT reviewer waives with reason
- Warning diagnostics require proportional handling by governance intensity
- diagnostics-report belongs in `.zoo-agent/runs/<run-id>/diagnostics-report.json`
- quality gate must read diagnostics-report when present
- unknown diagnostics must be recorded as `unknown`, not invented as pass
