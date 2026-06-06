# Implementation Queue Schema

The implementation queue is the handoff from planning to bounded execution.

Path:

- `.zoo-agent/runs/<run-id>/implementation-queue.json`
- `.zoo-agent/runs/<run-id>/implementation-queue.md`

## JSON Shape

```json
{
  "run_id": "",
  "goal_id": "",
  "items": [
    {
      "item_id": "",
      "branch_id": "",
      "task_id": "",
      "title": "",
      "type": "code",
      "status": "ready_for_worker",
      "root_goal_link": "",
      "acceptance_link": [],
      "obligation_link": [],
      "expected_artifacts": [],
      "preferred_executor": "codex",
      "allowed_files": [],
      "denied_files": [],
      "test_commands": [],
      "blocking_reason": "",
      "follow_up_reason": ""
    }
  ],
  "summary": {
    "code_items": 0,
    "test_items": 0,
    "docs_items": 0,
    "blocked_items": 0,
    "ready_for_worker": 0
  }
}
```

Executable leaf branches must generate queue items. Parent aggregation branches
do not enter the implementation queue directly.
