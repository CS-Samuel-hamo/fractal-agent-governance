# CLI-First Agent Runtime Usage

## Runtime Model

The CLI runtime is the control plane. Codex CLI is the bounded execution
backend. GPT is the final decision layer, DeepSeek is a cheap analysis worker,
and Zoo Code is an optional UI layer.

Default entrypoints:

```powershell
agent
agent "fix login bug"
agent bootstrap
agent run <input>
agent run --fast <input>
agent run --parallel <input>
agent run --governed <input>
agent status --run-id <run-id>
agent status --run-id <run-id> --no-write
agent rollback --run-id <run-id> --task-id <task-id> --dry-run
agent reroute --run-id <run-id> --task-id <task-id> --path governed
agent map check
agent review --run-id <run-id>
```

Running `agent` with no subcommand opens an interactive `agent>` shell.
Natural-language input is treated as `agent run "<input>"`. Built-ins are
`/status`, `/review`, `/reroute`, `/rollback`, `/exit`, and `/help`.
`agent "fix login bug"` is the same routing path as `agent run "fix login bug"`.

The preferred default path is:

```text
user input
-> CLI router
-> goal + loop system
-> task_classifier.py
-> fast | parallel | governed
-> Codex CLI execution backend
-> scope guard, tests, result, metrics
```

The preferred AI-native path for reversible bounded work is optimistic execution:

1. Zoo receives an intent.
2. `run_ai_native_task.py` builds a task context envelope from durable project context when available.
3. `run_ai_native_task.py` selects the cheapest safe execution path and writes an execution graph.
4. Reversible bounded work is routed to `run_optimistic_worker.py`.
5. The runner creates a temporary git worktree.
6. The runner generates a fast Codex Task Pack.
7. `run_codex_worker.py` runs `codex exec` inside the temporary worktree.
8. The external harness runs targeted tests, scope guard, and result collection.
9. The runner returns retry, escalation, or merge-candidate policy.

The current worker contract is code-only by default:

1. Zoo generates a bounded Codex Task Pack.
2. `run_codex_worker.py` runs `codex exec` in the target workspace or worktree.
3. Codex modifies only files allowed by `TASKS.yaml`.
4. Codex exits and writes `codex-run.json`, stdout/stderr, and `codex-final-message.md`.
5. The external harness runs targeted tests, scope guard, and result collection.

Do not rely on Codex itself to run pytest or scope guard on Windows. The harness owns verification.

## Task Context Envelope

The dispatcher does not first classify a request as short-term or long-term. It treats the user input as the current task and attaches durable project context as background:

- `.zoo-agent/project-charter.json`
- `.zoo-agent/current-run.json`
- `.zoo-agent/goals/*.json`
- `.zoo-agent/TASKS.md`
- `.zoo-agent/runs/<run-id>/TASKS.md`
- `.zoo-agent/project-readiness.json`
- `.zoo-agent/architecture-compatibility-report.json`
- `.zoo-agent/bootstrap/source-of-truth-resolver.json`

Generated context artifacts:

- `.zoo-agent/runs/<run-id>/task-contexts/<task-id>.json`
- `.zoo-agent/runs/<run-id>/task-contexts/<task-id>.md`
- `.zoo-agent/runs/<run-id>/task-context.json`
- `.zoo-agent/runs/<run-id>/task-context.md`

Pass `--goal-id <goal-id>` when the active goal is known. Project charter, goal contract, project profile, and project map stay read-only unless the user explicitly asks for durable state changes and `--allow-durable-state-update` is passed.

## Project Instructions And Map

`agent bootstrap` creates project-local instruction artifacts:

- `AGENTS.md` when missing, or `AGENTS.md.new` when refreshing an existing file.
- `.zoo-agent/code-standards.json` for layout, commands, coding rules,
  forbidden actions, done criteria, and runtime role definitions.
- `.zoo-agent/project-map.json` when no active map exists.

Maintenance commands:

```powershell
agent standards check --workspace <repo>
agent standards promote --workspace <repo>
agent map check --workspace <repo>
agent map refresh --workspace <repo>
agent map promote --workspace <repo>
```

`agent map check` blocks generated/runtime path contamination and warns when
the map digest is stale.

Before claiming worker, merge, deploy, release, or durable-state readiness,
check the context envelope for project readiness and architecture compatibility.
If Codex CLI is unavailable, if Level 0/1 trials are marked unsafe, or if the
compatibility report has unresolved issues, keep the run in governance-only or
planned-review mode until the relevant gate is cleared.

For Vibe-Coding-style requests, also apply
`docs/VIBE_CODING_CROSS_VALIDATION.md`: goal consistency, execution validity,
output correctness, state completeness, resource/dependency handling,
concurrency consistency, and repeatability must be known before claiming a
completed or merge-ready result.

## Execution Graph

`executor-selection.json` includes `execution_graph` for workflow design and scheduling:

- `chain_weight`: how heavy the selected chain is.
- `judgment_nodes`: how many decision gates were used and what each gate checked.
- `misroute_risk`: whether the route may be too light or too heavy.
- `parallel_contract.conflict_keys`: file-surface keys used to avoid conflicting parallel workers.
- `rollback_contract.mode`: how failure can be rolled back or gated.

Level 3 leaf skeletons include the same fields. Run leaves in parallel only when their conflict keys do not overlap.

Fast path is intentionally narrow. It may classify, create minimal Codex
execution context, run Codex, run scope guard, run known relevant tests, collect
results, and write a minimal report. It skips product doc generation, full
planning loops, fractal decomposition, implementation queues, governed review,
lesson extraction, eval suites, parent aggregation, and merge queue creation.

Parallel execution is conservative: unknown independence means not independent.
Workers require no shared files, no shared semantic resources, no shared API
contract, no shared DTO/schema, no shared database table, no shared fixture, no
dependency chain, and separate worktree/output/task-pack paths. Root, parent,
governance, review, and aggregation nodes are blocked from parallel workers.

## Move CODEX_HOME to D Drive

`CODEX_HOME` stores local Codex CLI state such as config, auth, logs, sessions, skills, and cache. Do not commit it to Git. Do not copy it into business projects. Do not print auth/token/config contents.

Recommended Windows setup:

```powershell
New-Item -ItemType Directory -Force -Path <CODEX_HOME>
[Environment]::SetEnvironmentVariable("CODEX_HOME", "<CODEX_HOME>", "User")
$env:CODEX_HOME = "<CODEX_HOME>"
```

Restart PowerShell, VS Code/Cursor, Zoo Code, and Codex App after changing the user-level environment variable.

## Generate a Task Pack

Most small bounded tasks should start with the optimistic runner:

```powershell
$dispatcher = if (Test-Path ".\scripts\run_ai_native_task.py") { ".\scripts\run_ai_native_task.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\run_ai_native_task.py" }
python $dispatcher `
  --run-id run-001 `
  --task-id task-001 `
  --workspace "<repo>" `
  --objective "Fix the branch summary API bug" `
  --allowed-file "src/api/**" `
  --allowed-file "tests/api/**" `
  --test-command "python -m pytest tests/api" `
  --codex-home <CODEX_HOME>
```

Use direct Task Pack generation when Zoo has already selected a planned or governed worker path.

For Level 2, Codex can still be invoked through the dispatcher:

```powershell
$dispatcher = if (Test-Path ".\scripts\run_ai_native_task.py") { ".\scripts\run_ai_native_task.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\run_ai_native_task.py" }
python $dispatcher `
  --run-id run-001 `
  --task-id task-002 `
  --workspace "<repo>" `
  --objective "Implement a bounded service change" `
  --governance-level 2 `
  --allowed-file "src/service/**" `
  --allowed-file "tests/service/**" `
  --test-command "python -m pytest tests/service" `
  --execute-planned
```

Level 3 should be decomposed into leaf tasks before Codex execution. The
dispatcher creates `.zoo-agent/runs/<run-id>/fractal-workstreams/<task-id>.json`
as the parent workstream artifact and generates draft leaf skeletons under
`.zoo-agent/runs/<run-id>/fractal-workstreams/<task-id>/leaf-tasks/`. Level 4
requires a human gate before any worker runs.

To run safe Level 3 leaves concurrently, first check the leaf index, then run
the parallel scheduler:

```powershell
python <USER_HOME>\.roo\agent-governance-kit\scripts\check_codex_worker_concurrency.py `
  --workspace "<repo>" `
  --run-id run-001 `
  --leaf-index ".zoo-agent\runs\run-001\fractal-workstreams\task-003\leaf-tasks\leaf-tasks.json"

python <USER_HOME>\.roo\agent-governance-kit\scripts\run_codex_parallel_workers.py `
  --workspace "<repo>" `
  --run-id run-001 `
  --leaf-index ".zoo-agent\runs\run-001\fractal-workstreams\task-003\leaf-tasks\leaf-tasks.json" `
  --max-workers 2 `
  --codex-home <CODEX_HOME>
```

The scheduler runs only safe leaf workers, each through its own dispatcher,
managed worktree, task pack, final-message file, result directory, and active
resource locks. It writes a record-only merge queue and parent aggregation;
merge remains a later serial integrator decision. See
`docs/CODEX_PARALLEL_WORKERS.md`.

## Governance Closure

After worker execution or parallel leaf execution, close the governance loop:

```powershell
agent status --workspace "<repo>" --run-id run-001
agent status --workspace "<repo>" --run-id run-001 --no-write
agent review --workspace "<repo>" --run-id run-001

python <USER_HOME>\.roo\agent-governance-kit\scripts\check_task_board_consistency.py `
  --workspace "<repo>" `
  --run-id run-001

python <USER_HOME>\.roo\agent-governance-kit\scripts\run_quality_gate.py `
  --workspace "<repo>" `
  --run-id run-001
```

`agent rollback` defaults to dry-run unless `--yes` is supplied. Rollback only
targets isolated managed worktrees under `.zoo-agent/worktrees`, writes a
rollback plan/patch, releases matching resource locks, and never runs
`git reset --hard`.

If risks remain, record or close them with `update_risk_register.py`. After the
quality gate passes and the parent aggregation is reviewed, explicitly
authorize merge queue processing:

```powershell
python <USER_HOME>\.roo\agent-governance-kit\scripts\run_quality_gate.py `
  --workspace "<repo>" `
  --run-id run-001 `
  --authorize-merge-queue

python <USER_HOME>\.roo\agent-governance-kit\scripts\process_merge_queue.py `
  --workspace "<repo>" `
  --run-id run-001 `
  --authorize `
  --authorization-note "Quality gate passed and parent aggregation reviewed"
```

This makes the queue processable for a serial integrator. It still does not
perform a git merge, deploy, release, provider probe, data update, cache
mutation, or durable-state write. See `docs/GOVERNANCE_CLOSURE.md`.

For a new or existing project, run the one-touch setup. This updates global
entrypoints, the installed governance kit, and the target project:

```powershell
python <USER_HOME>\.roo\agent-governance-kit\scripts\setup_zoo_agent.py `
  --project "<project>" `
  --mode auto
```

Equivalent command inside the project: run `agent-setup`, then reload.
This generates project context under `.zoo-agent/` and repairs local `.roo`
entrypoints without removing project-specific instructions.
Inactive rule/profile proposals are collected under `.zoo-agent/bootstrap/proposals/`.

Use `agent-bootstrap` only when the installed global kit is already current and
you only want to refresh project-local governance files.

After bootstrap, review `.zoo-agent/architecture-compatibility-report.md`.
The report is the guard against real-project drift from older governance-kit
versions: profile downgrade proposals, generated project-map contamination,
dual `.steward` / `.zoo-agent` source-of-truth ambiguity, and native dependency
ABI failures are recorded there before refreshed architecture claims are trusted.
The companion files are `.zoo-agent/bootstrap/scan-policy.json`,
`.zoo-agent/bootstrap/source-of-truth-resolver.json`,
`.zoo-agent/bootstrap/migration-report.md`, and
`.zoo-agent/bootstrap/rollback-anchor.md`.
The cross-project promotion map is
`docs/FIELD_FEEDBACK_INTEGRATION_MATRIX.md`; use it to check that field lessons
were promoted as process rules rather than business-domain assumptions.

```powershell
$taskpack = if (Test-Path ".\scripts\generate_codex_task_pack.py") { ".\scripts\generate_codex_task_pack.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\generate_codex_task_pack.py" }
python $taskpack `
  --run-id run-001 `
  --task-id task-001 `
  --objective "Fix the branch summary API bug" `
  --allowed-file "src/api/**" `
  --allowed-file "tests/api/**" `
  --denied-file ".env" `
  --denied-file "database/**" `
  --test-command "python -m pytest tests/api"
```

## Run Codex Worker

```powershell
$worker = if (Test-Path ".\scripts\run_codex_worker.py") { ".\scripts\run_codex_worker.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\run_codex_worker.py" }
python $worker `
  --task-dir ".zoo-agent\runs\run-001\codex-tasks\task-001" `
  --workspace "<worktree>" `
  --sandbox workspace-write `
  --codex-home <CODEX_HOME> `
  --timeout-seconds 360
```

PowerShell wrapper:

```powershell
.\wrappers\run_codex_worker.ps1 `
  -TaskDir ".zoo-agent\runs\run-001\codex-tasks\task-001" `
  -Workspace "<worktree>" `
  -CodexHome "<CODEX_HOME>" `
  -TimeoutSeconds 360
```

## Harness Verification

Run tests from the worktree:

```powershell
python -m pytest <targeted test path>
```

Run scope guard from the worktree:

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

Expected outputs:

- `codex-final-message.md`
- `codex-run.json`
- `codex-results/<task-id>/result.md`
- `codex-results/<task-id>/result.json`
- `ai-native-summary.json`
- `ai-native-summary.md`

`codex-results/<task-id>/result.json` also includes an environment fingerprint
with Python, Codex CLI, Node, Node ABI, npm, and `better-sqlite3` load status
when that native dependency is declared or installed. Treat Graph DB/SQLite
readiness as conditional if the native dependency probe fails.

`ai-native-summary.json` also includes governance state from run status, merge
queue, parent aggregation, risk register, project readiness, and task-board
consistency. Treat a `record-only` or non-processable merge queue as evidence,
not as merge approval.

