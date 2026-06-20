# Backend Plugins

Agent Runtime uses pluggable execution backends.

## User Commands

```powershell
agent backend list
agent backend switch <name>
agent backend health
```

## Included Backends

- `mock`: deterministic backend for product tests and demos.
- `dry_run`: no-op backend for safe analysis.
- `codex`: optional local execution backend plugin.

## Plugin Contract

Backends implement:

```python
ExecutionBackend.execute(task, context) -> ExecutionResult
```

Backends return the same schema, so the runtime can switch implementations without changing task flow.

## Adding a Backend

1. Implement the `ExecutionBackend` interface.
2. Return backend-neutral `ExecutionResult` fields.
3. Register the backend in `backend_registry.py`.
4. Add tests that compare schema compatibility with `mock`.

## Safety

Backend failures must return structured failure results. They must not produce false success or mutate runtime state outside the execution contract.
