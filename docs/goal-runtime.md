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
