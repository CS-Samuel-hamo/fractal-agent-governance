# CLI Reference

## Version

```powershell
agent --version
```

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
```

## Status

```powershell
agent status --workspace . --no-write
```
