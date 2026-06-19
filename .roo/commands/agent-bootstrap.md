# Agent Bootstrap

Project bootstrap for CLI-first Agent Runtime v4.0.

Use:

```powershell
agent bootstrap
```

or direct script form:

```powershell
python .\scripts\agent.py bootstrap --workspace "<workspace>"
```

## Expected Effects

- `.zoo-agent/runtime-v4.json` records the runtime model.
- `.zoo-agent/goals/<goal-id>.json` stores the active goal source of truth.
- `.zoo-agent/goal_state.json` points to the active goal.
- `.zoo-agent/current-run.json` records the active goal id.
- `.zoo-agent/loop_state.json` initializes convergence control.
- `.zoo-agent/metrics/agent-runtime-v4.json` initializes runtime metrics.
- `AGENTS.md` is created when missing; existing files get `AGENTS.md.new` on refresh.
- `.zoo-agent/code-standards.json` records local commands, coding rules, forbidden actions, and done criteria.
- `.zoo-agent/project-map.json` is created when no active project map exists.

Use `--with-project-bootstrap` only when legacy project facts, local `.roo`
entrypoints, or architecture compatibility artifacts also need refresh.

## Policy

- CLI is the primary runtime entrypoint.
- Zoo Code is optional UI, not the only control surface.
- Codex CLI is the execution backend, not the planner or orchestrator.
- GPT owns final decision-layer review for governed work.
- DeepSeek may be used for cheap analysis.
- Bootstrap is idempotent unless `--force` is passed.
- Use `--refresh-instructions` to regenerate AGENTS/code-standard proposals without overwriting active instructions.

