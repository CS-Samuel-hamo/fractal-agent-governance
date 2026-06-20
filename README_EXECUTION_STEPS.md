# CLI-First Agent Runtime + Codex CLI Backend

This starter pack runs as a CLI-first AI Agent Runtime. Zoo Code can visualize
or trigger the same flow, but it is no longer the only control entrypoint.

## Operating Model

```text
CLI Runtime = task routing, goal, loop, execution control
Codex CLI = execution backend
GPT = final decision layer
DeepSeek = cheap analysis worker
Zoo Code = optional UI layer
```

Codex Worker is intentionally code-only by default. It should implement the bounded task and exit. The harness then runs verification. This avoids Windows shell quoting and temporary-file issues inside `codex exec`, and it enables safer parallel workers.

## CLI Entrypoints

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

The CLI owns `/goal`, `/loop`, classification, path routing, status, rollback,
reroute, project-map checks, standards checks, review closure, and metrics. The
older `run_ai_native_task.py`, optimistic worker, and parallel worker scripts
remain execution backends behind `scripts/route_task.py`.

`agent bootstrap` also creates project-local instructions in the style of Codex
`/init`: `AGENTS.md` when missing, `.zoo-agent/code-standards.json`, and an
initial `.zoo-agent/project-map.json`. Existing `AGENTS.md` is not overwritten;
refreshes write `AGENTS.md.new` and `.zoo-agent/code-standards.json.new` for
explicit promotion.

## Move CODEX_HOME to D Drive

Move Codex CLI state to D drive when C drive space is tight:

```powershell
New-Item -ItemType Directory -Force -Path <CODEX_HOME>
[Environment]::SetEnvironmentVariable("CODEX_HOME", "<CODEX_HOME>", "User")
$env:CODEX_HOME = "<CODEX_HOME>"
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

## Governance Landing Conductor

Use `scripts/run_governance_landing.py` when a business project already has
approved governance planning artifacts and needs bounded project-map
contamination closure. The conductor replaces manual prompt chaining for this
lane: it reads only approved governance Markdown plus
`.zoo-agent/bootstrap/scan-policy.json`, promotes scan-policy/exclusion-policy
metadata when authorized, and writes a reviewer handoff.

```powershell
python scripts\run_governance_landing.py --project "<repo>" --mode status --json
python scripts\run_governance_landing.py --project "<repo>" --mode promote-scan-policy --json
python scripts\run_governance_landing.py --project "<repo>" --mode write-review --json
python scripts\run_governance_landing.py --project "<repo>" --mode full --json
```

The conductor reads project-map artifacts only in the explicitly authorized
project-map promotion/review phases. It does not read data/cache contents,
secrets, provider profiles, credentials, dependency internals, native module
internals, or merge queue contents. It does not run external scanner/rescan
commands, provider probes, data updates, product tests, cache mutation, runtime
materialization, merge, push, deploy, or release.

`full` advances this bounded lane through scan-policy review, proposal-only
path-metadata project-map generation, proposal review, active project-map
promotion, architecture post-review, and runtime/integration readiness
assessment. It still does not run provider/data/runtime/merge/deploy/release
actions; those remain separate authorization domains.

Recommended dispatcher:

```powershell
$dispatcher = if (Test-Path ".\scripts\run_ai_native_task.py") { ".\scripts\run_ai_native_task.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\run_ai_native_task.py" }
python $dispatcher `
  --run-id run-001 `
  --task-id task-001 `
  --workspace "<repo>" `
  --objective "Fix one bounded bug" `
  --allowed-file "src/**" `
  --allowed-file "tests/**" `
  --test-command "python -m pytest tests" `
  --codex-home <CODEX_HOME> `
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
agent status -> runtime-status.json
agent review -> runtime-review.json
agent rollback -> rollback/<task-id>.json
agent reroute -> route-audit/<task-id>.json
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
- `agent run <input>` is the default CLI runtime entrypoint; `.roo/commands/agent-run.md` is an optional UI bridge.
- `.roo/commands/codex-task.md`, `codex-run.md`, `codex-ingest.md`, and `codex-review.md` are lower-level manual controls.
- See `docs/ZOO_COMMAND_ENTRYPOINTS.md`.

Set up global kit and a project in one operation:

```powershell
python <USER_HOME>\.roo\agent-governance-kit\scripts\setup_zoo_agent.py `
  --project "<project>" `
  --mode auto
```

Equivalent command inside the project: run `agent-setup`, then reload.
Inactive proposals are collected under `.zoo-agent/bootstrap/proposals/`; active rules remain under `.roo/rules/`.

Use `agent-bootstrap` only when the global kit is already current and you only
need to refresh local project governance state.

Run optimistic worker:

```powershell
$optimistic = if (Test-Path ".\scripts\run_optimistic_worker.py") { ".\scripts\run_optimistic_worker.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\run_optimistic_worker.py" }
python $optimistic `
  --run-id run-001 `
  --task-id task-001 `
  --workspace "<repo>" `
  --objective "Fix one bounded bug" `
  --allowed-file "src/**" `
  --allowed-file "tests/**" `
  --test-command "python -m pytest tests" `
  --codex-home <CODEX_HOME> `
  --max-retries 1
```

Generate task pack:

```powershell
$taskpack = if (Test-Path ".\scripts\generate_codex_task_pack.py") { ".\scripts\generate_codex_task_pack.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\generate_codex_task_pack.py" }
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
$worker = if (Test-Path ".\scripts\run_codex_worker.py") { ".\scripts\run_codex_worker.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\run_codex_worker.py" }
python $worker `
  --task-dir ".zoo-agent\runs\run-001\codex-tasks\task-001" `
  --workspace "<worktree>" `
  --sandbox workspace-write `
  --codex-home <CODEX_HOME> `
  --timeout-seconds 360
```

Run scope guard:

```powershell
python "<task-dir>\check_codex_scope.py" task-001 --tasks "<task-dir>\TASKS.yaml"
```

Collect result:

```powershell
$collect = if (Test-Path ".\scripts\collect_codex_result.py") { ".\scripts\collect_codex_result.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\collect_codex_result.py" }
python $collect `
  --run-id run-001 `
  --task-id task-001 `
  --task-dir "<task-dir>" `
  --workspace "<worktree>"
```

Summarize an AI-native run:

```powershell
$summary = if (Test-Path ".\scripts\summarize_ai_native_run.py") { ".\scripts\summarize_ai_native_run.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\summarize_ai_native_run.py" }
python $summary `
  --run-id run-001 `
  --workspace "<repo>"
```

## Safety Rules

- Do not auto-merge.
- Do not auto-push.
- Do not use `danger-full-access` unless explicitly approved.
- Do not read or print secrets.
- Do not delete original `<USER_HOME>\.codex`.
- Do not modify business project code outside generated task scope.
- Prefer independent git worktrees for parallel Codex workers.

