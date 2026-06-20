# Backend Plugins

Agent Runtime uses pluggable execution backends.

## User Commands

```powershell
agent backend list
agent backend switch <name>
```

## Included Backends

- `mock`: deterministic backend for product tests and demos.
- `dry_run`: no-op backend for safe analysis.
- `codex`: optional local execution backend plugin.

## Adding a Backend

Backends are replaceable providers. A new backend should return the same result shape as the included backends, avoid false success, and keep failures structured so users can recover.

## Safety

Backend failures must return structured failure results. They must not produce false success or mutate runtime state outside the execution contract.
