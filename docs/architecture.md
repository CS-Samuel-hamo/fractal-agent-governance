# Architecture

Zoo Codex Worker Bridge is a CLI-first AI coding runtime.

```text
User
-> agent CLI
-> bootstrap / run / status / rollback / reroute / map / standards / review
-> goal + loop + classifier
-> fast | parallel | governed
-> Codex CLI backend / GPT final decision / optional Zoo Code UI
```

## Runtime Roles

- CLI Runtime: control plane.
- Codex CLI: execution backend for code changes, tests, and patch generation.
- GPT: final decision layer for governed tasks and readiness decisions.
- DeepSeek: cheap analysis or mechanical assistant.
- Zoo Code: optional visualization and control UI.

Planner, reviewer, integrator, and orchestrator are governance responsibilities inside the governed path, not separate runtime entrypoints.

## Runtime State

Runtime state lives under `.zoo-agent/`:

- `runtime-v4.json`
- `bootstrap.lock`
- `project-profile.json`
- `project-readiness.json`
- `bootstrap-report.md`
- `goal_state.json`
- `loop_state.json`
- `runs/<run-id>/...`

Business source directories are not edited during bootstrap.
