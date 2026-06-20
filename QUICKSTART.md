# Quickstart

## 1. Choose a Backend

```powershell
agent backend list
agent backend switch mock
```

Use `mock` or `dry_run` for first trials. Switch to a real backend only after dry-runs look correct.

## 2. Run a Task

```powershell
agent run "add a short README note" --workspace . --dry-run
```

The CLI prints a concise result:

```json
{
  "goal": "add a short README note",
  "progress": "complete",
  "result": "DRY_RUN_COMPLETE"
}
```

## 3. Set a Goal

```powershell
agent goal "make README onboarding clear"
agent run "improve README onboarding wording" --dry-run
```

## 4. Inspect Status

```powershell
agent status --workspace . --no-write
```
