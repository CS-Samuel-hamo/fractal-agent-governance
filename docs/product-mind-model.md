# Product Mind Model

Agent Runtime exposes a small user model:

```text
goal -> run -> result
```

## Goal

A goal is what the user wants to accomplish.

Example:

```powershell
agent goal "make README onboarding clear"
```

## Run

A run asks the runtime to work on a task.

Example:

```powershell
agent run "add a README troubleshooting note" --dry-run
```

## Result

A result is the outcome the user reviews.

Example result fields:

- `status`
- `goal`
- `run`
- `result`
- `artifacts`

## What Users Do Not Need To Learn

Normal users do not need to understand internal control modules, legacy compatibility tools, or execution internals. The CLI should keep the day-to-day model focused on goal, run, and result.

## Backends

Backends are selectable execution providers. Users only need to know which backends are available, which backend is selected, and whether the selected backend is healthy.
