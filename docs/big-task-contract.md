# Big Task Contract

The big task contract is stored at `.zoo-agent/runs/<run-id>/big-task-contract.json` and `.md`.

It records root goal, success criteria, non-goals, risk, readiness references, affected domains/resources, architecture/test/rollback capability, allowed execution mode, blockers, and next action.

The contract is an execution boundary. It is not a product document and does not authorize Codex actual execution on the root task.

## JSON Shape

```json
{
  "run_id": "",
  "goal_id": "",
  "raw_input": "",
  "root_goal": "",
  "success_criteria": [],
  "non_goals": [],
  "risk_level": "low|medium|high|critical",
  "project_readiness_ref": "",
  "backend_profile_ref": "",
  "loop_state_ref": "",
  "architecture_known": true,
  "test_capability": "known|partial|unknown",
  "rollback_capability": "known|partial|unknown",
  "affected_domains": [],
  "affected_resources": [],
  "requires_architecture_decision": false,
  "requires_human_gate": false,
  "allowed_execution_mode": "decomposition_only|leaf_dry_run|leaf_actual_allowed|blocked",
  "blocking_reasons": [],
  "next_action": ""
}
```

## Invariants

- The contract may authorize decomposition, but never root-task actual execution.
- `allowed_execution_mode=leaf_actual_allowed` still requires ready low-risk leaves and explicit user confirmation.
- Governance/runtime files are evidence, not business delivery.
- Parent aggregation is required before an integration worktree can be proposed.
