# Agent Runtime

CLI-first AI runtime with pluggable execution backend.

Status: `0.8.5-alpha`. This repository is ready for GitHub alpha publication and local controlled use. It is still an alpha tool: review outputs before applying or merging work.

## Three Commands

```powershell
agent run "fix bug"
agent pipeline "build feature"
agent goal "complete project"
```

The product mental model is intentionally small:

```text
User -> CLI -> Runtime -> Backend -> Result
```

- `goal`: what you want done.
- `run`: ask the runtime to work on it.
- `result`: review the outcome and artifacts.

## Install

```powershell
git clone <repo-url>
cd agent-runtime
.\bin\agent.cmd --version
```

Add `bin` to your user `PATH`, then use `agent` from any project workspace.

## Quickstart

```powershell
agent bootstrap --workspace .
agent backend list
agent backend switch mock
agent run "add a short README note" --workspace . --dry-run
agent status --workspace . --no-write
```

For a real backend, select one explicitly:

```powershell
agent backend switch codex
agent run "fix typo in README" --workspace . --dry-run
```

Actual execution is opt-in through the runtime command flags and should start with low-risk, tightly scoped files.

## Backends

Included backend plugins:

- `mock`: deterministic local test backend.
- `dry_run`: no-op backend for safe planning and demos.
- `codex`: optional local execution plugin.

The runtime core talks to backends through one execution interface. A backend failure should not corrupt runtime state or produce false success.

## Safety

- No automatic merge.
- No automatic push.
- No deployment or production migration.
- No secret, API key, token, or `.env` content reading.
- Rollback defaults to dry-run.
- Runtime artifacts are written under `.zoo-agent/`.

## Documentation

- [INSTALL.md](INSTALL.md)
- [QUICKSTART.md](QUICKSTART.md)
- [EXAMPLES.md](EXAMPLES.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [CLI_REFERENCE.md](CLI_REFERENCE.md)
- [BACKEND_PLUGINS.md](BACKEND_PLUGINS.md)
- [docs/product-mind-model.md](docs/product-mind-model.md)
