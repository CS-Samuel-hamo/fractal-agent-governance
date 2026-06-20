# Goal State Ownership Policy

## Single Writer

Only `scripts/goal_state_manager.py` is allowed to make final writes to multi-goal state.

All other modules are read-only or proposal-only for canonical state:

- `goal_loop_engine.py`
- `run_parent_aggregation_gate.py`
- `goal_completion_detector.py`
- `global_loop_engine.py`
- `goal_scheduler.py`
- `goal_conflict_detector.py`
- `route_task.py`
- `agent.py`

Those modules may write run-scoped evidence, proposals, reports, state patches, and event logs. They must not replace `.zoo-agent/goal/goal_state.json` with a single-goal payload.

## Sticky Fields

These fields must be preserved unless an explicit validated patch changes them:

- `goal.priority`
- `goal.status`
- `goal.resource_usage`
- `goal.depends_on`
- `goal.blocks`
- `goal.created_at`
- `goal.manual_priority`
- `goal.blocking_reason`
- `goal.backlog_reason`
- `goal.human_decision_required`
- `goal.risk_level`

## Forbidden Implicit Conversions

These conversions are forbidden without an explicit patch and reason:

- `blocked -> paused`
- `blocked -> active`
- `backlog -> paused`
- `backlog -> active`
- `completed -> active`
- `completed -> paused`
- any priority reset to `50`
- resource usage reset to `[]`
- dependency/block lists reset to `[]`

## Legal Conversions

Legal transitions must pass through `goal_state_manager` patch application:

- `active -> completed`
- `active -> blocked`
- `active -> paused`
- `paused -> active`
- `paused -> backlog`
- `paused -> completed` with explicit user or aggregation reason
- `backlog -> active` with scheduler or user reason
- `blocked -> paused` with unblock reason
- `blocked -> backlog` with defer reason
