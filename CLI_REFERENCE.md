# CLI Reference

## Version

```powershell
agent --version
```

## Bootstrap

```powershell
agent bootstrap --workspace .
```

Prepares runtime metadata for a workspace.

## Run

```powershell
agent run "<task>" --workspace . --dry-run
```

Runs a task and prints a concise result.

## Pipeline

```powershell
agent pipeline "<task>" --workspace . --dry-run
```

Explicit product pipeline command. Most users can use `agent run`.

## Goal

```powershell
agent goal "<goal>"
agent goal show
agent goal list
```

## Backend

```powershell
agent backend list
agent backend switch mock
agent backend health
```

## Status

```powershell
agent status --workspace . --no-write
```

## Rollback Plan

```powershell
agent rollback --workspace . --run-id <run-id> --task-id <task-id> --dry-run
```

## Compatibility Commands

Older analysis commands remain available for debugging and regression tests. They are not required for normal product use.
