# Diagnostics Quality Gate

Diagnostics are quality-gate input.

- collect before/after diagnostics when available
- new Error diagnostics block integration unless GPT reviewer waives with reason
- Warning diagnostics require proportional handling by governance intensity
- diagnostics-report belongs in `.zoo-agent/runs/<run-id>/diagnostics-report.json`
- branch diagnostics belong in `.zoo-agent/runs/<run-id>/branches/<branch-id>/diagnostics-report.json`
- aggregation diagnostics belong in `.zoo-agent/runs/<run-id>/aggregation-diagnostics-report.json`
- quality gate must read diagnostics-report when present
- parent aggregation gate must read aggregation diagnostics before merge queue is allowed to proceed
- unknown diagnostics must be recorded as `unknown`, not invented as pass
