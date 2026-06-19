# CLI-First Agent Runtime v4.0

This kit is now a CLI-first AI Agent Runtime.

## Runtime Model

```text
CLI Runtime = routing, goal, loop, execution control
Codex CLI = execution backend
GPT = final decision layer
DeepSeek = cheap analysis worker
Zoo Code = optional visualization / control UI
```

Zoo Code is not the only control entrypoint. The CLI is the primary runtime
entrypoint; UI commands may call the same CLI scripts but should not own the
execution model.

## Commands

```powershell
agent bootstrap
agent run <input>
agent run --fast <input>
agent run --parallel <input>
agent run --governed <input>
agent status --run-id <run-id>
agent rollback --run-id <run-id> --task-id <task-id> --dry-run
agent reroute --run-id <run-id> --task-id <task-id> --path governed
agent map check
agent review --run-id <run-id>
```

On Windows, `agent.cmd` dispatches to `scripts/agent.py`. Shell users can call
`./agent` or `wrappers/agent.sh`.

## Flow

```text
user input
-> scripts/agent.py
-> scripts/route_task.py
-> /goal via set_goal.py and get_goal.py
-> /loop via loop_state.json
-> classifier via task_classifier.py
-> fast | parallel | governed execution path
```

## Goal System

Goal state is the source of truth:

- `scripts/set_goal.py` writes `.zoo-agent/goals/<goal-id>.json`.
- `scripts/get_goal.py` resolves the active goal.
- `scripts/check_goal_alignment.py` records task/review alignment evidence.
- `route_task.py` binds every CLI task to a `goal_id`.
- Codex task packs record the bound `goal_id` in `TASKS.yaml` and
  `task-metadata.json`.

Review and merge decisions should inspect
`.zoo-agent/runs/<run-id>/goal-alignment/<task-id>.json`.
`scripts/run_quality_gate.py` treats missing or blocked goal-alignment evidence
as a default blocker for observed tasks.

## Project Instructions

`agent bootstrap` also initializes project-local instructions in the spirit of
Codex `/init`:

- `AGENTS.md` is created when missing.
- Existing `AGENTS.md` is not overwritten; refresh writes `AGENTS.md.new`.
- `.zoo-agent/code-standards.json` records layout, commands, forbidden actions,
  done criteria, and the five runtime roles.
- Use `agent standards check` and `agent standards promote` to validate or
  activate proposals.

The runtime role set is fixed:

- CLI Runtime owns routing, goal, loop, execution control, status, rollback,
  review, and metrics.
- Codex CLI is the execution backend only.
- GPT is the decision layer.
- DeepSeek is the cheap analysis worker.
- Zoo Code is an optional UI layer.

Planner, orchestrator, reviewer, and integrator are governed-path
responsibility labels, not additional runtime entrypoints.

## Loop System

`loop_state.json` prevents endless planning or optimization loops:

```json
{
  "iteration": 0,
  "max_iteration": 10,
  "status": "active",
  "drift_detected": false
}
```

When iteration exceeds `max_iteration`, the CLI runtime marks drift and routes
the task to the governed path for GPT decision-layer review.

## Path Contracts

Fast path is the default for low-coupling, low-uncertainty, low-blast-radius
work. It calls Codex through the existing fast backend, then relies on scope
guard and tests. It does not decompose or expand product documents.

Parallel path is allowed only when tasks are independent, conflict keys do not
overlap, and each worker gets its own worktree, task pack, output files, and
result path.

Governed path is reserved for complex or risky work. It records goal alignment,
decomposition, implementation queue, Codex worker evidence, reconciliation,
parent aggregation, merge queue evidence, and a GPT review requirement.

## Recovery And Governance Commands

`agent status` summarizes runtime marker, goal, loop, code standards, project
map alignment, metrics, CLI reports, goal alignment, worktrees, risk register,
task-board consistency, quality gate, and merge queue state.

`agent rollback` removes only managed worktrees under `.zoo-agent/worktrees/`
and releases matching task locks. It does not run `git reset --hard`, delete
project source, merge, deploy, release, or mutate durable state.

`agent reroute` preserves old evidence under the original run and writes
`route-audit/<task-id>.json` before launching the selected path again.

`agent map check|refresh|promote` keeps `.zoo-agent/project-map.json` aligned
with current source roots while excluding generated and runtime paths.

`agent review` runs task-board consistency and quality-gate closure checks and
records `runtime-review.json`. Review evidence is not merge authorization.

## Metrics

Runtime metrics are written to `.zoo-agent/metrics/agent-runtime-v4.json`:

- `fast_path_rate`
- `parallel_execution_rate`
- `governed_path_rate`
- `codex_latency`
- `doc_overproduction_rate`
- `code_delivery_rate`

