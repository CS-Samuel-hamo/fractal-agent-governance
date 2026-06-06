# Changelog

## v0.3.12

- Added the Implementation Delivery Kernel so implementation work moves from planning into implementation queues, Codex task packs, code/test/config delivery, and code delivery gates.
- Added `/implement` as an explicit delivery shortcut while keeping `/agent-run` as the main workflow bus.
- Added implementation queue generation, queue validation, Codex task-pack promotion, doc-only completion checks, root-goal alignment checks, code delivery gate checks, follow-up backlog generation, and an implementation delivery smoke test.
- Extended Codex task generation/result collection with implementation item IDs, root-goal links, queue status updates, and no-doc-only delivery enforcement.
- Extended progress snapshots, task boards, and the launcher with delivery status, implementation queue actions, Codex pack generation from queue, and code delivery gate controls.
- Preserved high-risk gates: secret reads, `.env` reads, provider probes, data updates, cache mutation, dependency install/rebuild, merge, push, deploy, release, destructive cleanup, and production data migration still require separate explicit authorization.

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
