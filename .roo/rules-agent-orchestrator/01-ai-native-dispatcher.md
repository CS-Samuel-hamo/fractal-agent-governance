# CLI-First Runtime Dispatcher Rule

Normal execution should route through:

```powershell
agent run <input>
```

Direct router fallback:

```powershell
$router = if (Test-Path ".\scripts\route_task.py") { ".\scripts\route_task.py" } else { "<USER_HOME>\.roo\agent-governance-kit\scripts\route_task.py" }
python $router --workspace "<workspace>" --input-text "<input>"
```

The router owns:

- active goal resolution and goal alignment
- loop convergence state
- task classification into `fast`, `parallel`, or `governed`
- execution path control
- runtime metrics

Do not bypass the CLI router for normal Level 0/1 work. `run_ai_native_task.py`,
`run_optimistic_worker.py`, and `run_codex_parallel_workers.py` are backend
execution tools behind the router.

Parallel scheduling must use `check_codex_worker_concurrency.py` and
`run_codex_parallel_workers.py`; do not start raw parallel `codex exec`
processes from the parent workspace.

Governed work must produce implementation queue, parent aggregation, merge
queue evidence, and GPT review evidence before completion or integration
claims.

