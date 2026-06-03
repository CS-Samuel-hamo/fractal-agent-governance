# Diagnostics Aggregation Policy

Diagnostics exist at two levels.

Branch diagnostics:

- Run inside each worktree or branch.
- Stored at `.zoo-agent/runs/<run-id>/branches/<branch-id>/diagnostics-report.json`.

Aggregation diagnostics:

- Run after parent aggregation or merge candidate generation.
- Stored at `.zoo-agent/runs/<run-id>/aggregation-diagnostics-report.json`.

Rules:

- Child branch diagnostics pass does not imply parent integration diagnostics pass.
- New Error diagnostics block integration unless GPT reviewer explicitly waives them.
- Warning handling depends on governance intensity.
- `quality-gate.py` reads branch diagnostics.
- `parent-aggregation-gate.py` reads aggregation diagnostics.
- Diagnostics unknown blocks high-risk integration.
