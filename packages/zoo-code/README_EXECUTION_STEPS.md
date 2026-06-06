# Zoo Governance Runtime + Codex CLI Worker

This starter pack wires Zoo Code governance to Codex CLI bounded execution.

## Operating Model

```text
Zoo Code = governance control plane
Codex CLI = bounded code worker
External harness = tests, scope guard, result collection
```

Codex Worker is intentionally code-only by default. It should implement the bounded task and exit. The harness then runs verification. This avoids Windows shell quoting and temporary-file issues inside `codex exec`, and it enables safer parallel workers.

## Move CODEX_HOME to D Drive

Move Codex CLI state to D drive when C drive space is tight:

```powershell
New-Item -ItemType Directory -Force -Path D:\AI_DEV\codex_home
[Environment]::SetEnvironmentVariable("CODEX_HOME", "D:\AI_DEV\codex_home", "User")
$env:CODEX_HOME = "D:\AI_DEV\codex_home"
```

`CODEX_HOME` may contain config, auth, logs, sessions, skills, and cache. Do not commit it, copy it into business projects, or print auth/token/config contents.

Restart PowerShell, VS Code/Cursor, Zoo Code, and Codex App after setting the user-level variable.

## Daily Flow

AI-native optimistic tasks:

```text
Zoo receives intent
-> cheap hard-risk gate
-> build task context envelope
-> attach execution graph
-> create temporary worktree
-> run fast Codex worker
-> run targeted tests and scope guard
-> retry, escalate, or produce merge candidate
```

The dispatcher does not first classify the request as short-term or long-term. It treats the user input as the current task, then attaches durable project context as background from `.zoo-agent/project-charter.json`, `.zoo-agent/current-run.json`, `.zoo-agent/goals/*.json`, and task boards when present.

Generated context files:

- `.zoo-agent/runs/<run-id>/task-contexts/<task-id>.json`
- `.zoo-agent/runs/<run-id>/task-contexts/<task-id>.md`

Durable state is read-only unless the user explicitly asks to update it and the dispatcher is called with `--allow-durable-state-update`.

Daily management should start from the integrated board:

```powershell
$board = if (Test-Path ".\scripts\render_governance_board.py") { ".\scripts\render_governance_board.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\render_governance_board.py" }
python $board --workspace "<repo>" --run-id run-001
```

Read `.zoo-agent/BOARD.md` for durable aim, active goal, task progress,
execution evidence, governance gates, and next actions. Continue editing task
intent in `.zoo-agent/TASKS.md` or `.zoo-agent/runs/<run-id>/TASKS.md`; the
board itself is generated.

Each dispatcher selection also writes `execution_graph` into `.zoo-agent/runs/<run-id>/executor-selection.json`. Use it to inspect chain weight, judgment nodes, misroute risk, conflict keys, parallel contract, and rollback mode. Level 3 leaf skeletons carry their own execution graph, so light leaves can still use the AI-native loop even when the parent workstream is heavy.

Real business projects need three closure checks before any merge or release
claim:

```text
execution closure: worker actually ran, or the run is explicitly governance-only
evidence closure: reviewer evidence, tests, quality gates, and run JSON agree
integration closure: merge queue is processable and the final gate authorizes it
```

If `codex` is unavailable, `project-readiness.json` blocks Level 0/1 trials, or
`merge-queue.json` is record-only/non-processable, the run may still have useful
planning or reviewer evidence, but it is not a merge, deploy, release, provider
probe, data update, cache mutation, or durable-state approval.

Recommended dispatcher:

```powershell
$dispatcher = if (Test-Path ".\scripts\run_ai_native_task.py") { ".\scripts\run_ai_native_task.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\run_ai_native_task.py" }
python $dispatcher `
  --run-id run-001 `
  --task-id task-001 `
  --workspace "<repo>" `
  --objective "Fix one bounded bug" `
  --allowed-file "src/**" `
  --allowed-file "tests/**" `
  --test-command "python -m pytest tests" `
  --codex-home D:\AI_DEV\codex_home `
  --max-retries 1
```

Level 2 planned execution can still call Codex. Use `--governance-level 2`
and `--execute-planned`; the dispatcher runs Codex in an isolated worktree with
the full prompt and harness verification.

Level 3+ should not be executed as one broad Codex task. Level 3 creates a
fractal governed path with draft leaf skeletons. Each leaf should be re-routed
through `run_ai_native_task.py`, usually as Level 0/1. Level 4 requires a human gate.

Small Level 0/1 tasks:

```text
Prefer `run_ai_native_task.py`.
It selects the cheapest safe path. Bounded reversible work flows into
`run_optimistic_worker.py`; harder work falls back to a planned task pack.
```

Large Level 3+ tasks:

```text
Zoo decomposes work
-> safe leaf tasks become Codex Task Packs
-> each leaf runs in an independent git worktree
-> Codex workers may run concurrently
-> harness verifies each leaf
-> parent aggregation and integration remain sequential and gated
```

Use `check_codex_worker_concurrency.py` before `run_codex_parallel_workers.py`.
The parallel scheduler writes resource locks, a branch schedule, worker logs,
record-only merge queue evidence, and parent aggregation evidence. It never
authorizes merge by itself.

Governance closure commands:

```text
check_task_board_consistency.py -> task-board-consistency.json
update_risk_register.py -> risk-register.json
run_quality_gate.py -> quality-gate.json
process_merge_queue.py -> merge-queue-processing.json
manage_resource_locks.py -> .zoo-agent/locks/resource-locks.json
```

`run_quality_gate.py --authorize-merge-queue` records queue-processing
authorization only after evidence passes. `process_merge_queue.py` turns a
record-only queue into a serial integrator contract, but it still does not run
`git merge`, deploy, release, provider probes, data updates, cache mutation, or
durable-state writes.

## Commands

Zoo/Roo command entrypoints:

- `.roo/commands/agent-setup.md` performs one-touch global kit sync plus project bootstrap.
- `.roo/commands/agent-bootstrap.md` performs one-step setup for new and existing projects.
- `.roo/commands/agent-board.md` renders the integrated governance board.
- `.roo/commands/agent-run.md` is the default AI-native entrypoint.
- `.roo/commands/codex-task.md`, `codex-run.md`, `codex-ingest.md`, and `codex-review.md` are lower-level manual controls.
- See `docs/ZOO_COMMAND_ENTRYPOINTS.md`.

Set up global kit and a project in one operation:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\setup_zoo_agent.py `
  --project "<project>" `
  --mode auto
```

Equivalent command inside the project: run `agent-setup`, then reload.
Inactive proposals are collected under `.zoo-agent/bootstrap/proposals/`; active rules remain under `.roo/rules/`.

Use `agent-bootstrap` only when the global kit is already current and you only
need to refresh local project governance state.

Run optimistic worker:

```powershell
$optimistic = if (Test-Path ".\scripts\run_optimistic_worker.py") { ".\scripts\run_optimistic_worker.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\run_optimistic_worker.py" }
python $optimistic `
  --run-id run-001 `
  --task-id task-001 `
  --workspace "<repo>" `
  --objective "Fix one bounded bug" `
  --allowed-file "src/**" `
  --allowed-file "tests/**" `
  --test-command "python -m pytest tests" `
  --codex-home D:\AI_DEV\codex_home `
  --max-retries 1
```

Generate task pack:

```powershell
$taskpack = if (Test-Path ".\scripts\generate_codex_task_pack.py") { ".\scripts\generate_codex_task_pack.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\generate_codex_task_pack.py" }
python $taskpack `
  --run-id run-001 `
  --task-id task-001 `
  --objective "Fix one bounded bug" `
  --allowed-file "src/**" `
  --allowed-file "tests/**" `
  --denied-file ".env" `
  --test-command "python -m pytest tests"
```

Run worker:

```powershell
$worker = if (Test-Path ".\scripts\run_codex_worker.py") { ".\scripts\run_codex_worker.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\run_codex_worker.py" }
python $worker `
  --task-dir ".zoo-agent\runs\run-001\codex-tasks\task-001" `
  --workspace "<worktree>" `
  --sandbox workspace-write `
  --codex-home D:\AI_DEV\codex_home `
  --timeout-seconds 360
```

Run scope guard:

```powershell
python "<task-dir>\check_codex_scope.py" task-001 --tasks "<task-dir>\TASKS.yaml"
```

Collect result:

```powershell
$collect = if (Test-Path ".\scripts\collect_codex_result.py") { ".\scripts\collect_codex_result.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\collect_codex_result.py" }
python $collect `
  --run-id run-001 `
  --task-id task-001 `
  --task-dir "<task-dir>" `
  --workspace "<worktree>"
```

Summarize an AI-native run:

```powershell
$summary = if (Test-Path ".\scripts\summarize_ai_native_run.py") { ".\scripts\summarize_ai_native_run.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\summarize_ai_native_run.py" }
python $summary `
  --run-id run-001 `
  --workspace "<repo>"
```

## Safety Rules

- Do not auto-merge.
- Do not auto-push.
- Do not use `danger-full-access` unless explicitly approved.
- Do not read or print secrets.
- Do not delete original `$env:USERPROFILE\.codex`.
- Do not modify business project code outside generated task scope.
- Prefer independent git worktrees for parallel Codex workers.
