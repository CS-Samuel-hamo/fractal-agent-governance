# Project Architecture Map

The project architecture map is the long-lived project fact layer for module ownership, file locations, entrypoints, tests, docs, and coarse dependencies.

It is separate from task plans and code style policy:

- `project-profile.json` records technology facts: language, framework, package manager, commands, roots, and risk paths.
- `project-map.json` records architecture facts: modules, owned paths, files, entrypoints, tests, docs, dependencies, and unknowns.
- `architecture-boundaries.json` records dependency direction and layer assignments.
- `AGENTS.md` and local project rules record human-readable project conventions and coding policy.
- `TASKS.md` records the current run plan and user intervention state.
- `resource-locks.json` records resources touched by one run or branch schedule.

Do not mix these layers. A coding convention is not a module fact. A current task status is not a project architecture fact. A run resource lock is not permanent ownership.

## Required Use

For non-trivial coding, `/agent-run` should ensure:

1. `.zoo-agent/project-profile.json` exists.
2. `.zoo-agent/project-map.json` exists and is not stale.
3. `.zoo-agent/architecture-boundaries.json` exists or architecture status is explicitly `unknown`.
4. Changed files can be mapped to a module before review.
5. Unknown module ownership, dependency direction, or high-risk architecture boundaries trigger GPT planner/reviewer escalation.

## Update Policy

The map is updated by events, not by continuous background mutation:

- first governance intake
- before non-trivial coding when missing or stale
- after creating, moving, or deleting source/test/docs/config files
- before review when changed files are not mapped
- before integration when resource locks or branch ownership depend on module boundaries

The generator skips secret-like files by name and must not read `.env`, key, token, credential, private, `.pem`, or `.key` contents.

## Relationship To Fractal Branches

The branch manager uses the project map to draft:

- `owned_paths`
- `shared_paths`
- provider/consumer assumptions
- branch boundaries
- resource locks
- parallel denial reasons
- parent aggregation ownership matrices

If the project map is unknown or stale, low-risk single-file work may proceed with a warning, but multi-module, public API, Proc/data-source, DTO/schema, security, auth, payment, PII, migration, or architecture-boundary work must stop for project-map refresh or GPT decision.
