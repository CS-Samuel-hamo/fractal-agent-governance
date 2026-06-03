# AI-Native Dispatcher Rule

The orchestrator should route normal task execution through:

```powershell
$dispatcher = if (Test-Path ".\scripts\run_ai_native_task.py") { ".\scripts\run_ai_native_task.py" } else { "$env:USERPROFILE\.roo\agent-governance-kit\scripts\run_ai_native_task.py" }
python $dispatcher ...
```

Use the local workspace dispatcher when present. Otherwise use the installed global governance kit dispatcher.

Dispatcher outputs:

- `executor-selection.json`
- `executor-selection.json.execution_graph` with chain weight, judgment nodes, misroute risk, conflict keys, parallel contract, and rollback contract
- `task-contexts/<task-id>.json` and `task-contexts/<task-id>.md`
- `dispatcher-runs/<task-id>.json`
- `optimistic-runs/<task-id>.json` when an optimistic or planned isolated worker runs
- `fractal-workstreams/<task-id>.json` for Level 3 parent tasks
- `fractal-workstreams/<task-id>/leaf-tasks/leaf-tasks.json` for Level 3 leaf drafts
- `ai-native-summary.json`
- `task-board-consistency.json`
- `risk-register.json` when risks are known
- `quality-gate.json`
- `merge-queue-processing.json` when queue processing is authorized

Do not bypass the dispatcher for Level 0/1 work unless the user explicitly requests a raw Codex CLI action.

The dispatcher should not ask a separate model call to decide whether the user's request is long-term or short-term. The current request is the current task; durable goal and project files are context, not replacement objectives.

For parallel scheduling, use `execution_graph.parallel_contract.conflict_keys`. Tasks with overlapping conflict keys should not run concurrently unless the parent explicitly marks them read-only.

When executing Level 3 leaves concurrently, use
`scripts/check_codex_worker_concurrency.py` before
`scripts/run_codex_parallel_workers.py`. Do not start raw parallel `codex exec`
processes from the parent workspace.

After worker execution, run `check_task_board_consistency.py` and
`run_quality_gate.py` before claiming completion or merge readiness. Use
`update_risk_register.py` for known run risks. Use `process_merge_queue.py`
only after the quality gate authorizes queue processing.
