# Branch Scheduler Schema

Runtime artifact: `.zoo-agent/runs/<run-id>/branch-schedule.json`

```json
{
  "run_id": "",
  "parallel_allowed_by": "agent-branch-manager",
  "parallel_groups": [
    {
      "group_id": "group-1",
      "decision_owner": "agent-branch-manager",
      "decision_model": "GPT-5.5",
      "branches": ["branch-a", "branch-b"],
      "requires_worktree": true,
      "risk_level": "low",
      "status": "scheduled"
    }
  ],
  "branches": [
    {
      "branch_id": "",
      "owned_paths": [],
      "shared_paths": [],
      "forbidden_paths": [],
      "provides": [],
      "consumes": [],
      "dependencies": [],
      "acceptance_criteria": [],
      "verification_plan": [],
      "risk_level": "low",
      "sensitive_flags": [],
      "worktree": "",
      "quality_gate_status": "unknown",
      "review_status": "unknown"
    }
  ]
}
```
