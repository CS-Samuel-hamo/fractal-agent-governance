# Project Architecture Map

For non-trivial coding, keep project facts separate from task state and code style policy.

Canonical project fact artifacts:

- `.zoo-agent/project-profile.json`: technology profile, commands, roots, and risk paths.
- `.zoo-agent/project-map.json`: modules, owned paths, files, entrypoints, tests, docs, dependencies, and unknowns.
- `.zoo-agent/project-map.md`: human-readable module map.
- `.zoo-agent/architecture-boundaries.json`: dependency direction and module layer assignments.

Do not place current task status in project-map files. Do not place coding style preferences in project-map files. Use `AGENTS.md`, local project rules, or code-style skills for conventions.

Before multi-module, public API, DTO/schema, Proc/data-source, security, auth, payment, PII, migration, or architecture-boundary changes:

1. Ensure project profile exists.
2. Ensure project map exists and is not stale.
3. Ensure changed files map to known modules.
4. Ensure architecture boundaries are known or explicitly escalated.
5. Use project-map module ownership to derive branch `owned_paths`, `shared_paths`, resource locks, and parent aggregation ownership matrices.

If project map is missing or stale, run `scripts/generate-project-map.py` or stop for GPT planner/user decision. DeepSeek may draft the map but must not approve unknown high-risk boundaries.
