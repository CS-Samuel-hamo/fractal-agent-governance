# AI-Native Execution Loop

This bridge should optimize for cheap isolated attempts, not heavy pre-approval.

## Default Loop

```text
Intent
-> cheap hard-risk gate
-> task context envelope
-> execution graph
-> temporary git worktree
-> fast Codex worker
-> harness verification
-> retry / escalate / merge candidate
```

## Context Envelope

Do not run a separate classifier to decide whether the user's request is short-term or long-term. The current user request is the current task.

Before path selection and task-pack generation, `scripts/run_ai_native_task.py` writes a task context envelope:

- `.zoo-agent/runs/<run-id>/task-contexts/<task-id>.json`
- `.zoo-agent/runs/<run-id>/task-contexts/<task-id>.md`
- `.zoo-agent/runs/<run-id>/task-context.json`
- `.zoo-agent/runs/<run-id>/task-context.md`

The envelope includes durable background when present:

- `.zoo-agent/project-charter.json`
- `.zoo-agent/current-run.json`
- `.zoo-agent/goals/*.json`
- `.zoo-agent/TASKS.md`
- `.zoo-agent/runs/<run-id>/TASKS.md`

Workers may use this context to split and guide work, but must not rewrite project charter, goal contracts, project profile, or project map unless the user explicitly requests a durable state update and the dispatcher was called with `--allow-durable-state-update`.

## Architecture Compatibility

`scripts/agent_bootstrap.py` writes an architecture compatibility report after
project bootstrap and local entrypoint repair:

- `.zoo-agent/architecture-compatibility-report.json`
- `.zoo-agent/architecture-compatibility-report.md`
- `.zoo-agent/installed-kit-version.json`
- `.zoo-agent/bootstrap/scan-policy.json`
- `.zoo-agent/bootstrap/source-of-truth-resolver.json`
- `.zoo-agent/bootstrap/migration-report.md`
- `.zoo-agent/bootstrap/rollback-anchor.md`

Treat `ready_with_architecture_blocks` as installed-but-not-trusted for
architecture claims. Do not rely on refreshed profile, project map, Graph DB,
or native runtime readiness until the report is resolved.

## Execution Graph

Path selection does not call another model to deliberate. It attaches a deterministic `execution_graph` to `.zoo-agent/runs/<run-id>/executor-selection.json`.

The graph records:

- `chain_weight`: `light`, `medium`, `heavy_parent_light_leaves`, or `blocked_until_approval`.
- `judgment_nodes`: context envelope, optional governance hint, hard-risk gate, scope/surface gate, verification gate, and any decomposition or human gate.
- `misroute_risk`: estimated chance the route is too light or too heavy.
- `parallel_contract`: whether it may run in parallel and which `conflict_keys` it owns.
- `rollback_contract`: whether failure can be handled by discarding an isolated worktree, staying at task-pack-only, or stopping at a human gate.

Level 3 parent chains are heavy, but generated leaves carry their own execution graph and usually become light or medium tasks. Leaves can run concurrently only when their conflict keys do not overlap.

## Path Selection

Use the optimistic path by default when the task is reversible and bounded:

- local bug fixes
- routine refactors
- UI or test updates with clear scope
- small feature changes with targeted tests

Use the planned or governed path when the task touches irreversible or high-cost areas:

- auth, security, permissions, or secret handling
- payment, billing, PII, or privacy
- database migrations or schema changes
- production config, deployment, or release flow
- public API breaking changes
- broad architecture changes

When Zoo already knows the governance level, pass `--governance-level` to the
dispatcher:

- Level 0/1: `optimistic_worker` unless a hard-risk rule is hit.
- Level 2: `planned_worker`; Codex can still run with `--execute-planned`, but
  it uses the full prompt and an isolated worktree.
- Level 3: `fractal_governed`; generate planned artifacts and decompose into
  executable leaf task skeletons.
- Level 4: `human_gate`; stop before execution.

## Optimistic Worker

`scripts/run_ai_native_task.py` is the recommended dispatcher. It writes
`.zoo-agent/runs/<run-id>/task-contexts/<task-id>.json`,
`.zoo-agent/runs/<run-id>/executor-selection.json` with `execution_graph`, then dispatches:

- `optimistic_worker`: run the isolated optimistic loop.
- `planned_worker`: generate a full task pack for governed execution.
- `fractal_governed`: generate a full task pack and expect leaf decomposition.
- `human_gate`: stop before execution.

After each dispatcher run, `scripts/summarize_ai_native_run.py` refreshes:

- `.zoo-agent/runs/<run-id>/ai-native-summary.json`
- `.zoo-agent/runs/<run-id>/ai-native-summary.md`

Closure-sensitive runs should then execute:

- `scripts/check_task_board_consistency.py`
- `scripts/update_risk_register.py` when risks are known
- `scripts/run_quality_gate.py`
- `scripts/process_merge_queue.py` after explicit queue-processing authorization

These write task-board, risk, quality gate, and serial queue-processing
artifacts. They do not merge, deploy, release, probe providers, mutate data or
cache, or write durable project state by themselves.

Level 3 dispatcher runs also create:

- `.zoo-agent/runs/<run-id>/fractal-workstreams/<task-id>.json`
- `.zoo-agent/runs/<run-id>/fractal-workstreams/<task-id>.md`
- `.zoo-agent/runs/<run-id>/fractal-workstreams/<task-id>/leaf-tasks/leaf-tasks.json`

After reviewing and refining leaf skeletons, use
`scripts/check_codex_worker_concurrency.py` and
`scripts/run_codex_parallel_workers.py` to run non-overlapping leaves
concurrently. The scheduler creates resource locks, worker logs, record-only
merge queue evidence, and parent aggregation evidence. It does not merge.

`scripts/run_optimistic_worker.py` owns the optimistic execution loop:

1. Performs a cheap hard-risk check against the objective and allowed file scope.
2. Creates a managed git worktree under `.zoo-agent/worktrees/<run>/<task>/`.
3. Generates a Codex Task Pack with the fast prompt template.
4. Runs `scripts/run_codex_worker.py` inside the isolated worktree.
5. Runs configured harness test commands.
6. Runs result collection, including scope guard.
7. Writes a policy result:
   - `merge_candidate`
   - `merge_candidate_partial`
   - `retryable_test_failure`
   - `retryable_worker_failure`
   - `escalate_scope_violation`
   - `blocked_by_hard_risk_gate`

## Example

```powershell
$dispatcher = if (Test-Path ".\scripts\run_ai_native_task.py") { ".\scripts\run_ai_native_task.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\run_ai_native_task.py" }
python $dispatcher `
  --run-id run-001 `
  --task-id task-001 `
  --workspace "<repo>" `
  --objective "Fix the branch summary rendering bug" `
  --allowed-file "src/**" `
  --allowed-file "tests/**" `
  --test-command "python -m pytest tests" `
  --codex-home D:\AI_DEV\codex_home `
  --max-retries 1
```

Use `--dry-run` to inspect routing without creating a worktree or calling Codex.

Level 2 isolated execution:

```powershell
$dispatcher = if (Test-Path ".\scripts\run_ai_native_task.py") { ".\scripts\run_ai_native_task.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\run_ai_native_task.py" }
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

## Failure Policy

Fast failures should not become incidents:

- Test failure: retry once with failure output when `--max-retries 1` is enabled.
- Scope violation: stop and escalate; do not retry blindly.
- Worker failure: retry only when the output suggests a transient or repairable issue.
- Hard-risk gate: move to planned/governed execution unless explicitly approved.

## Design Boundary

Codex is responsible for fast bounded implementation.

Zoo is responsible for:

- worktree isolation
- worker scheduling
- verification orchestration
- retry and escalation policy
- result collection
- review and merge candidate tracking
