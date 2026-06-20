# Goal State Patch Schema

State patches are the only cross-module update format for canonical multi-goal state.

```json
{
  "patch_id": "",
  "created_at": "",
  "source": "goal_loop",
  "reason": "",
  "base_revision": 0,
  "changes": [
    {
      "goal_id": "",
      "op": "set_status",
      "from": "",
      "to": "",
      "requires_explicit_reason": true,
      "reason": ""
    }
  ]
}
```

Supported operations:

- `set_status`
- `set_progress`
- `set_active`
- `set_priority`
- `set_resource_usage`
- `append_event`
- `set_blocker`
- `set_backlog`
- `set_completion`
- `set_loop_status`
- `freeze_actual_execution`

Patch application rules:

- `base_revision` must match the current state revision.
- Sticky-field changes require explicit reason.
- Illegal status transitions are rejected.
- Successful application increments `revision`.
- Every applied change appends an event to `event_log`.
- Failed invariant checks reject the write.
