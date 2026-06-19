# Goal And Loop Runtime

Every run is bound to a `goal_id`.

Goal state:

- `.zoo-agent/goals/<goal-id>.json`
- `.zoo-agent/goal_state.json`
- `.zoo-agent/runs/<run-id>/goal-alignment/*.json`

Loop state:

- `.zoo-agent/loop_state.json`
- `.zoo-agent/runs/<run-id>/loop_state.json`

The loop prevents endless planning or local optimization. When iteration limits are exceeded, the runtime escalates or records local optimization as follow-up.

Doc-only coding tasks are tracked with `doc_only_task_rate` and `code_delivery_gate`.
