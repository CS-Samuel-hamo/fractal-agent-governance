# Multi-goal State Invariants

The invariant checker verifies multi-goal scheduler state before and after aggregation, scheduling, conflict resolution, and global loop changes.

Required invariants:

- Goal IDs are unique.
- Every goal has a status.
- At most one goal is active by default.
- Completed goals are not active.
- Critical conflict goals must not become active silently.
- Priority must not reset to `50` without a `set_priority` event.
- Blocked goals must not become paused without a reason.
- Backlog goals must not become paused without a reason.
- Resource usage must not be cleared or rewritten without a `set_resource_usage` event.
- Status transitions must have event-log evidence.

Use:

```powershell
python scripts\check_goal_state_invariants.py --workspace <repo>
python scripts\check_goal_state_invariants.py --workspace <repo> --before <before-goal-state.json>
```

The second form detects 0.7.1-style state pollution by comparing sticky fields before and after a run.
