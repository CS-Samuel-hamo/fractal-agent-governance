# Quickstart

## 1. Bootstrap

```powershell
agent bootstrap --workspace .
```

Bootstrap writes runtime metadata under `.zoo-agent/`. It does not edit business source code.

## 2. Pick a Backend

```powershell
agent backend list
agent backend switch mock
```

Use `mock` or `dry_run` for first trials. Switch to a real backend only after dry-runs look correct.

## 3. Run a Task

```powershell
agent run "add a short README note" --workspace . --dry-run
```

The CLI prints a concise result:

```json
{
  "status": "ok",
  "goal": {"task": "add a short README note"},
  "run": {"mode": "dry_run"},
  "result": {"verdict": "DRY_RUN_COMPLETE"}
}
```

## 4. Set a Goal

```powershell
agent goal "make README onboarding clear"
agent run "improve README onboarding wording" --dry-run
```

## 5. Inspect Status

```powershell
agent status --workspace . --no-write
```
