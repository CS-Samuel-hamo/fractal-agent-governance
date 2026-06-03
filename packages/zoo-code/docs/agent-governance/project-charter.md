# Project Charter Layer

The project charter is the long-lived project constitution. It answers why the project exists, who it serves, what success means, what is out of scope, what quality bar applies, and when the agent must stop or ask.

It is not a task board and not a module map.

Canonical files:

- `.zoo-agent/project-charter.json`: machine-readable charter facts.
- `docs/project-charter.md`: human-readable charter.
- `.zoo-agent/goals/<goal-id>.json`: per-goal contract bound to the charter.
- `.zoo-agent/runs/<run-id>/TASKS.md`: current run plan and intervention surface.

## Separation Of Concerns

- Project charter: durable intent and decision boundaries.
- Goal contract: one target outcome and verifiable completion criteria.
- Project profile: technology stack and commands.
- Project map: modules, paths, entrypoints, tests, docs, and dependencies.
- Architecture boundaries: allowed dependency direction.
- Local rules / `AGENTS.md`: coding conventions and local policy.
- Task board: current run status and user intervention.

Do not put current branch statuses in the charter. Do not put file inventories in the charter. Do not put coding style detail in the charter unless it is a project-level quality principle.

## Required Fields

- mission
- target users
- product goals
- technical goals
- non-goals
- success criteria
- quality bar
- architecture principles
- data and security constraints
- risk tolerance
- human gates
- fallback / abort conditions
- decision owners
- open questions

Unknown is acceptable during intake, but material unknowns block non-trivial coding unless the user or GPT planner explicitly accepts the risk.

## Runtime Rules

First-run intake should create or bind the project charter before coding. `/agent-run` may proceed with read-only discovery when the charter is missing, but non-trivial coding requires a charter or explicit `charter_unknown` escalation.

Goal contracts must align with the charter. If a goal conflicts with mission, non-goals, quality bar, data/security constraints, or human gates, the run must stop for GPT planner or user decision.
