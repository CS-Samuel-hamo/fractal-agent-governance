# Governance Intensity Levels

Governance intensity is selected from risk, coupling, reversibility, validation speed, and uncertainty. The selected level must be recorded in `.zoo-agent/runs/<run-id>/governance-intensity.json`.

| Level | Name | Use When | Required Path | Forbidden Shortcuts |
| --- | --- | --- | --- | --- |
| 0 | Micro Edit | Comment, small doc edit, formatting, no behavior change | project profile if available, micro execution, diff summary, optional test | no high-risk paths, no shared interfaces, no production config |
| 1 | Routine Coding | Small bugfix or small feature following an existing pattern | mini obligation check, bounded execution, targeted test, mechanical review | no public API, no migration, no auth/security/payment/PII |
| 2 | Multi-surface Feature | API/service/test/DTO/schema/registry/provider or other propagation surface | goal-lite, full obligation ledger, GPT planner approval, quality gate, GPT reviewer | cannot skip obligation coverage or review |
| 3 | Fractal Workstream | Multiple system boundaries, multiple risks, more than 8 projected files, unknowns, Proc/data-source mismatch | goal, root branch, fractal decomposition, child execution, parent aggregation, integration gate | no direct integration without parent aggregation |
| 4 | High-risk / Irreversible Change | Auth, payment, PII, migration, security, production config, breaking public API | full governance, ADR/security/release readiness, rollback, human gate where required | no DeepSeek final approval, no ordinary exception for high-risk gate |

## Classification Factors

- changed surface count
- projected file count
- shared type or public API impact
- security, data, migration, production config risk
- architecture uncertainty
- test availability
- rollback ease
- existing pattern availability
- owned_paths clarity
- user-facing behavior ambiguity

## Required Output

The classifier must output:

```json
{
  "run_id": "",
  "branch_id": "root",
  "level": 2,
  "level_name": "Multi-surface Feature",
  "rationale": [],
  "required_gates": [],
  "triggered_gates": [],
  "blocked_shortcuts": [],
  "created_by_mode": "agent-orchestrator",
  "model": "GPT-5.5"
}
```

If classification confidence is low, choose the higher level and record `classification_uncertainty`.
