# Changelog

## v0.3.11

- Added executable governance closure checks for task-board consistency, risk register updates, quality gates, and merge queue processing.
- Added active resource-lock acquisition/release around parallel Codex workers.
- Added AI-native run summaries that surface quality-gate status and active lock counts.
- Added governance closure documentation and updated usage, command entrypoint, operating model, parallel worker, and cross-validation docs.
- Expanded smoke coverage for active lock conflicts, task-board warnings, open-risk quality gate blocking, quality gate authorization, and merge queue artifacts.

## v0.3.10

- Added one-command project bootstrap for new and existing projects.
- Added project-level `.zoo-agent/TASKS.md` and `.zoo-agent/current-run.json`.
- Added Codex CLI worker bridge task packs, scope guard, dry-run execution, and result collection.
- Hardened `AGENTS.md`, local rule, and `.gitignore` proposal behavior to avoid overwriting existing project files.
- Improved task-board export/apply consistency checks.
- Improved artifact graph and runtime consistency compatibility for older run graphs.
- Hardened parallel branch safety with resource-lock coverage checks.

## v0.1.0-alpha

- Initial public release candidate.
- Added Zoo Code adapter package.
- Added toy examples for implicit work discovery, fractal decomposition, proc/data source mismatch, and worktree parallel exploration.
- Added eval suites and demo scripts.
