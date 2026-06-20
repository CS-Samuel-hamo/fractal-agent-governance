# Architecture

Agent Runtime is a CLI-first runtime engine with replaceable execution backends.

```text
User -> CLI -> Runtime -> Backend -> Result
```

## Runtime Core

The runtime core owns the product API:

- `run_task`
- `run_pipeline`
- `run_goal`
- `get_status`
- `switch_backend`

## Execution Interface

Execution backends implement a single contract:

```python
ExecutionBackend.execute(task, context) -> ExecutionResult
```

The runtime does not depend on a specific backend implementation.

## Result Contract

Runtime-facing execution results use backend-neutral fields:

- `backend_type`
- `backend_status`
- `backend_returncode`
- `execution_status`
- `diff`
- `confidence`
- `execution_time`
- `notes`

## Safety Model

The runtime is conservative by default:

- dry-run is supported everywhere
- actual execution should be scoped
- no automatic merge
- no automatic push
- no secret content reads
- rollback defaults to dry-run
