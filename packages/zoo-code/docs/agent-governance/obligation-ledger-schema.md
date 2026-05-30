# Obligation Ledger Schema

Every non-trivial coding task must create `.zoo-agent/runs/<run-id>/obligation-ledger.json` before implementation.

```json
{
  "run_id": "",
  "branch_id": "",
  "task_summary": "",
  "explicit_request": [],
  "implicit_obligations": [
    {
      "obligation_id": "",
      "category": "",
      "description": "",
      "why_required": "",
      "source_signal": "",
      "candidate_files_or_surfaces": [],
      "status": "required",
      "owner_mode": "",
      "verification": "",
      "evidence": "",
      "risk_if_omitted": "",
      "escalation_required": false
    }
  ],
  "not_applicable_decisions": [
    { "category": "", "reason": "", "evidence": "" }
  ],
  "deferred_items": [
    { "item": "", "reason": "", "owner": "", "follow_up_required": true }
  ]
}
```

Required obligations are closed only when `verification` and `evidence` identify concrete checks or changed artifacts. `not_applicable` requires evidence. `deferred` requires owner and reason. `escalated` requires an escalation artifact or id.
