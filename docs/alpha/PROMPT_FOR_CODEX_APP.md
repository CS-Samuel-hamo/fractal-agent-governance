# CLI-First Agent Runtime v4.0 Prompt

Use this kit as a CLI-first AI Agent Runtime.

## Runtime Roles

- CLI runtime: control plane for routing, goal, loop, execution control, status, rollback, review, and metrics.
- Codex CLI: execution backend for code changes, patch generation, and harness-driven tests.
- GPT: final decision layer for governed work and review.
- DeepSeek: cheap analysis worker.
- Zoo Code: optional UI layer only.

## Required Entrypoints

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

Do not require Zoo Code UI to control execution. Do not require a task id from
the user on the default path. Do not start with a planning loop for bounded
work.

## Runtime Flow

```text
user input
-> CLI router
-> /goal source of truth
-> /loop convergence control
-> task classifier
-> fast | parallel | governed
-> Codex CLI backend where execution is allowed
-> scope guard, tests, result collection, metrics
```

## Hard Rules

- Every task must bind to a `goal_id`.
- Every review must inspect goal alignment evidence.
- Fast path is default for low-coupling, low-uncertainty, low-blast-radius work.
- Parallel path is allowed only for independent tasks with disjoint conflict keys and separate worktrees/output paths.
- Governed path is reserved for complex or risky work and must end in GPT review evidence.
- Codex CLI is never the planner or orchestrator.
- Planner, orchestrator, reviewer, and integrator are governed-path responsibilities, not runtime entrypoints.
- Rollback may only discard managed worktrees and release locks; it must not reset or delete project source.
- Metrics must track fast path rate, parallel execution rate, governed path rate, Codex latency, doc overproduction rate, and code delivery rate.

