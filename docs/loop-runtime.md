# Loop Runtime

`/loop` is the convergence and loss-control layer, not a planner.

Primary file:

`.zoo-agent/loop/loop-state.json`

Legacy-compatible file:

`.zoo-agent/loop_state.json`

Commands:

- `agent loop status`
- `agent loop reset`
- `agent loop set --max-iterations 5`
- `agent loop stop`
- `agent loop explain`

Rules:

- Delivered work can converge the loop.
- Two no_delivery outcomes stop actual execution until the task is clarified.
- Two backend failures switch the runtime toward dry-run/manual task pack.
- Repeated doc-only coding work suggests an implementation pass.
- Repeated local optimization is moved to follow-up.
- Exceeding max iterations stops automatic execution and asks for `/loop explain`.

## Big Task Loop

Big task loop state is stored per run at `.zoo-agent/runs/<run-id>/loop-state.json`.

Additional fields:

- `phase`: readiness, decomposition, leaf_dry_run, leaf_actual, aggregation, integration_check
- `decomposition_rounds` / `max_decomposition_rounds`
- `leaf_redo_count` / `max_leaf_redo_count`

Default decomposition rounds are limited to 2. Repeated no-delivery or backend failures stop actual execution and move the run to clarification, dry-run, or manual task pack. Local optimization that does not advance the root goal becomes follow-up work.
