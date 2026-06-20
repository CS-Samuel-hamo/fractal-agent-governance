# Runtime Engine Productization

Agent Runtime 0.8 separates runtime control from execution backends.

## Architecture

```text
runtime_core
  -> execution_interface
  -> backend_registry
  -> codex | mock | dry_run backend plugins
```

The runtime core owns goal, task, and pipeline API calls. The execution layer owns backend invocation only.

## Runtime API

- `RuntimeCore.run_goal(goal)`
- `RuntimeCore.run_task(task)`
- `RuntimeCore.run_pipeline(input)`
- `RuntimeCore.get_status()`
- `RuntimeCore.switch_backend(name)`
- `RuntimeCore.pause()`
- `RuntimeCore.resume()`

## Execution Interface

All execution backends implement:

```python
ExecutionBackend.execute(task, context) -> ExecutionResult
```

The pipeline executor calls the selected backend through this interface. It does not need to know whether the backend is Codex, mock, dry-run, or a future executor.

## Backend Plugins

Included backends:

- `codex`: wraps the existing Codex worker path.
- `mock`: deterministic test backend that can deliver or fail without Codex.
- `dry_run`: no-op backend for analysis and product tests.

Codex is now a replaceable execution plugin, not a runtime-core dependency.

## Safety

The productized runtime keeps the existing safety boundaries:

- no automatic merge
- no automatic push
- no worktree deletion
- no secret or `.env` reading
- verifier still consumes `execution_result.json`
- scheduler, goal loop, and big-task systems remain outside executor responsibility
