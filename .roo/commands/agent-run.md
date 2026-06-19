# Agent Run

Default CLI-first runtime entrypoint for AI-native task handling.

Zoo/Roo can invoke this command, but the control plane is the CLI runtime:

```text
CLI runtime -> goal + loop -> classifier -> fast | parallel | governed
Codex CLI -> execution backend
GPT -> final decision layer
DeepSeek -> cheap analysis worker
Zoo Code -> optional UI layer
```

## Dispatcher Resolution

Resolve the router in this order:

1. If `<workspace>\scripts\route_task.py` exists, use it.
2. Otherwise use `<USER_HOME>\.roo\agent-governance-kit\scripts\route_task.py`.
3. If neither exists, stop and report the missing router.

The lower-level `run_ai_native_task.py` dispatcher remains an execution backend
behind the CLI router.

## Command Shape

```powershell
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

Direct script form:

```powershell
$router = if (Test-Path ".\scripts\route_task.py") { ".\scripts\route_task.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\route_task.py" }
python $router `
  --workspace "<workspace>" `
  --input-text "<input>" `
  --goal-id "<goal-id>" `
  --allowed-file "src/**" `
  --allowed-file "tests/**" `
  --test-command "python -m pytest tests"
```

## Goal And Loop

Every CLI task must bind to a `goal_id`. If no active goal exists, the CLI
runtime creates one with `scripts/set_goal.py` semantics and records it under
`.zoo-agent/goals/`.

The runtime writes:

- `.zoo-agent/goal_state.json`
- `.zoo-agent/current-run.json`
- `.zoo-agent/loop_state.json`
- `.zoo-agent/runs/<run-id>/loop_state.json`
- `.zoo-agent/runs/<run-id>/goal-alignment/<task-id>.json`

Reviewers must inspect goal alignment before completion or integration claims.

## Path Policy

Fast path is the default when coupling, uncertainty, blast radius, and
dependency risk are low. It maps to Codex direct execution through the existing
fast backend and must not perform planning, decomposition, product doc
expansion, or task splitting.

Parallel path is allowed only when independent tasks have no shared files,
schema/API/DB surfaces, dependency chain, or shared output paths. Each worker
must get a separate worktree, task pack, final message, result path, and active
resource lock.

Governed path is reserved for complex work. It records goal alignment,
decomposition, implementation queue, Codex worker evidence, reconciliation,
parent aggregation, merge queue evidence, and GPT review.

## Status Sources

- `.zoo-agent/runs/<run-id>/cli-runtime/<task-id>.json`
- `.zoo-agent/runs/<run-id>/goal-alignment/<task-id>.json`
- `.zoo-agent/runs/<run-id>/implementation-queue.json`
- `.zoo-agent/runs/<run-id>/parent-aggregation.json`
- `.zoo-agent/runs/<run-id>/merge-queue.json`
- `.zoo-agent/runs/<run-id>/gpt-review.json`
- `.zoo-agent/metrics/agent-runtime-v4.json`
- `.zoo-agent/runs/<run-id>/runtime-status.json`
- `.zoo-agent/runs/<run-id>/runtime-review.json`
- `.zoo-agent/runs/<run-id>/rollback/<task-id>.json`
- `.zoo-agent/runs/<run-id>/route-audit/<task-id>.json`

Before claiming completion or merge readiness, also inspect quality gate,
risk-register, task-board consistency, and merge queue processing evidence.
The quality gate checks goal-alignment evidence by default.

Rollback may only discard managed worktrees under `.zoo-agent/worktrees/` and
release task locks. It must not reset, delete source, merge, deploy, or release.

