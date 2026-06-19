# Leaf Task Contract

Leaf contracts live under `.zoo-agent/runs/<run-id>/leaf-tasks/`.

Each leaf records objective, task type, risk, owned resources, allowed/denied files, provides/consumes, acceptance, test policy, rollback note, preferred route, readiness reference, and execution mode.

Codex task packs may only be generated from leaf tasks that pass the task readiness gate.

## JSON Shape

```json
{
  "leaf_id": "",
  "run_id": "",
  "parent_goal_id": "",
  "objective": "",
  "task_type": "code|test|docs|config|research|review|integration|blocked",
  "risk_level": "low|medium|high|critical",
  "owned_resources": [],
  "allowed_files": [],
  "denied_files": [],
  "provides": [],
  "consumes": [],
  "acceptance": [],
  "test_policy": "required|optional|not_applicable|unknown",
  "test_commands": [],
  "rollback_note": "",
  "preferred_route": "fast|parallel|governed|dry_run_only",
  "task_readiness_ref": "",
  "execution_allowed": false,
  "execution_mode": "dry_run_only|actual_allowed|blocked",
  "blocking_reasons": []
}
```

## Execution Rules

- No acceptance means no execution.
- No allowed/denied scope means no execution.
- High or critical risk leaves cannot run Codex actual.
- Research, review, parent, aggregation, and integration leaves are not Codex code-execution leaves.
- `READY_FOR_ACTUAL_CODEX` is a leaf-level condition only; parent aggregation must still pass later.
