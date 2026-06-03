# Branch Scheduler Schema

Runtime artifact: `.zoo-agent/runs/<run-id>/branch-schedule.json`

```json
{
  "run_id": "",
  "parallel_allowed_by": "agent-planner",
  "parallel_approval_model": "GPT-5.5",
  "direct_parallel_merge_allowed": false,
  "requires_merge_queue": true,
  "requires_parent_aggregation": true,
  "phases": [
    {
      "phase_id": "phase-001",
      "execution_mode": "parallel",
      "branch_ids": ["branch-a", "branch-b"],
      "requires_parent_aggregation": true
    }
  ],
  "parallel_groups": [
    {
      "group_id": "phase-001",
      "decision_owner": "agent-planner",
      "decision_model": "GPT-5.5",
      "approval_status": "approved",
      "branches": ["branch-a", "branch-b"],
      "requires_worktree": true,
      "requires_checkpoint_before_execution": true,
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

Generation command:

```bash
python scripts/schedule-parallel-branches.py --run-id <run-id> --goal-id <goal-id> --branch-tree <branch-tree.json>
```
