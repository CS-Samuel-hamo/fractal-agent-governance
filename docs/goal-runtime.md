# Goal Runtime

`/goal` is the global objective anchor for CLI-first runtime work.

Primary file:

`.zoo-agent/goal/current-goal.json`

Legacy-compatible files are still written under `.zoo-agent/goals/` and `.zoo-agent/goal_state.json`.

Commands:

- `agent goal set "<goal>"`
- `agent goal show`
- `agent goal clear`
- `agent goal status`
- Interactive: `/goal <goal>`

Every run binds a `goal_id`. Simple tasks may infer a transient goal. Governed work must have a reviewable goal. Fast path uses lightweight token overlap only; it does not run a long planning loop.

## Big Task Goal Contract

For big tasks, the active goal must be explicit. The runtime does not silently create a transient goal for `agent plan-big` or big governed work.

The big task goal fields are:

- `goal_id`
- `root_goal`
- `success_criteria`
- `non_goals`
- `business_outcome`
- `technical_outcome`
- `risk_tolerance`
- `created_at`
- `updated_at`

Every generated leaf task must reference `parent_goal_id`, success criteria IDs, and inherited non-goals. Parent aggregation checks goal coverage before an integration worktree can be proposed.
