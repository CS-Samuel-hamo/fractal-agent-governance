# Diagnostics Quality Gate

Zoo Code / VS Code diagnostics are quality signals.

Rules:

1. Executor should record diagnostics before and after edits when available.
2. New Error diagnostics block integration unless GPT reviewer explicitly waives them.
3. Warning diagnostics are judged by governance intensity:
   - Level 0/1: record and continue unless warning is in changed paths.
   - Level 2: require explanation or targeted fix.
   - Level 3/4: require GPT reviewer decision.
4. `quality-gate.py` reads diagnostics report when present.
5. `/agent-run` may request `@problems` or equivalent diagnostics context.

Diagnostic report path:

`.zoo-agent/runs/<run-id>/diagnostics-report.json`

Schema:

```json
{
  "run_id": "",
  "branch_id": "",
  "before": {"error_count": 0, "warning_count": 0},
  "after": {"error_count": 0, "warning_count": 0},
  "new_errors": [],
  "new_warnings": [],
  "status": "pass|fail|warning|unknown"
}
```
