# Three-stage pipeline runtime

Agent Runtime now has a compressed execution path:

```text
goal -> planner -> executor -> verifier
```

The pipeline is the preferred simplified path for low-latency operation. Legacy 0.7.x governance scripts remain available as compatibility tools, but they are no longer required as independent runtime stages for the pipeline path.

## Planner

Script: `scripts/pipeline_planner.py`

Planner responsibilities:

- Read the active or requested goal.
- Classify the task.
- Build a lightweight decomposition.
- Build a lightweight resource graph.
- Build a conflict report.
- Emit a single `plan.json`.

Planner must not execute Codex, aggregate results, run tests, mutate goal state, or manage the loop.

## Executor

Script: `scripts/pipeline_executor.py`

Executor responsibilities:

- Read `plan.json`.
- Execute the plan leaf contracts.
- Invoke Codex only when actual execution is explicitly allowed.
- Emit `execution_result.json`.

Executor must not schedule goals, select goals, detect conflicts, aggregate parent results, or decide goal completion.

## Verifier

Script: `scripts/pipeline_verifier.py`

Verifier responsibilities:

- Read `execution_result.json`.
- Verify execution outcomes.
- Collapse delivery, aggregation, goal completion, and integration-candidate checks into one final verification result.
- Emit `final_result.json`.

Verifier must not plan, spawn Codex, schedule goals, or mutate execution.

## Simple Loop

Script: `scripts/pipeline_loop.py`

The loop only orchestrates stage flow:

```text
while not goal.converged:
    planner -> executor -> verifier
```

It does not own scheduler state, goal state, conflict state, or backend policy state. The default max iteration is `1`, which keeps the runtime deterministic and prevents accidental multi-layer looping.

## CLI

```powershell
agent pipeline "fix README wording only" --workspace <repo> --dry-run
```

Actual Codex execution is disabled unless both the plan allows actual execution and the user passes `--allow-actual`.
