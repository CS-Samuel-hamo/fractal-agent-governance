# Field Feedback Integration Matrix

This matrix records the architecture and process lessons promoted from the two
real business-project scans. Business-domain details stay in project-local
field reports; only reusable governance/runtime lessons are promoted into the
global kit and governance package.

## Promotion Rule

A field finding is promoted only when it changes how the kit should route,
bootstrap, verify, summarize, or integrate work across projects. Product
semantics, domain vocabulary, and one-off app contracts remain local context.

## Integrated Lessons

| Generalized lesson | Promotion target | Verification |
| --- | --- | --- |
| Current `.zoo-agent` runtime facts must outrank legacy governance evidence for active execution. | `scripts/agent_bootstrap.py` writes `.zoo-agent/bootstrap/source-of-truth-resolver.json`; `scripts/build_task_context.py` carries it into task contexts. | `scripts/smoke_test.py` asserts resolver artifacts and dual-state issue detection. |
| Bootstrap must not silently downgrade a high-confidence project profile. | `scripts/agent_bootstrap.py` scores active profiles and blocks lower-information proposals. | Smoke asserts `profile_downgrade_proposal` and `frontend_stack_lost_in_profile_proposal`. |
| Generated/runtime paths must not become source roots, module owners, or API entrypoints. | `scan-policy.json` plus project-map contamination checks in `scripts/agent_bootstrap.py`. | Smoke asserts generated-path scan policy and contamination issue detection. |
| Worker readiness is an explicit runtime fact, not an assumption. | Codex CLI probes, Windows shim fallbacks, and `.zoo-agent/project-readiness.json` checks. | Smoke asserts readiness-block issue detection; docs require governance-only/planned-review mode when blocked. |
| Review evidence is not merge, deploy, release, provider-probe, data-update, cache-mutation, or durable-state approval. | `scripts/summarize_ai_native_run.py`, reviewer rule, integrator merge policy, and usage docs. | Summary smoke covers governance-state collection; rules require processable merge queue and final gate. |
| Dirty retired governance paths, generated data, suspicious root artifacts, and local rule changes require path-scoped attribution. | Compatibility report issue checks and integrator staging policy. | Smoke asserts retired-path, runtime-data, suspicious-root, and governance-runtime issue detection. |
| Upgrades need migration and rollback anchors, not only copied commands. | One-touch setup, `migration-report.md`, `rollback-anchor.md`, and installed kit version artifacts. | Smoke asserts artifacts and rollback scope text. |
| Local project `.roo` files may shadow global entrypoints. | `scripts/sync_zoo_entrypoints.py` injects dispatcher override blocks and bridge shim rules. | Smoke asserts local override preservation and idempotent project sync. |
| Execution graphs must make routing, parallelism, and rollback inspectable. | `scripts/execution_policy.py` and dispatcher artifacts. | Smoke asserts graph, conflict keys, Level 3 leaf graphs, and rollback modes. |
| Environment evidence should be captured without creating false readiness blocks for unused native dependencies. | Bootstrap and Codex result collection record Python, Codex CLI, Node, npm, and declared/installed `better-sqlite3` only. | Smoke and collection checks verify environment fingerprints. |
| Vibe Coding work needs explicit failure-mode cross-validation. | `docs/VIBE_CODING_CROSS_VALIDATION.md`, reviewer rule, and integrator merge policy. | Starter-pack validation requires the checklist; reviewer/integrator rules reference its dimensions. |
| Codex CLI can be a parallel worker, but the CLI runtime must own scheduling. | `scripts/check_codex_worker_concurrency.py`, `scripts/run_codex_parallel_workers.py`, and `docs/CODEX_PARALLEL_WORKERS.md`. | Smoke validates schedule/resource-lock artifacts and worker dry-run execution. |
| Governance concepts must have executable closure, not only reviewer text. | `scripts/check_task_board_consistency.py`, `scripts/update_risk_register.py`, `scripts/run_quality_gate.py`, `scripts/process_merge_queue.py`, `scripts/manage_resource_locks.py`, and `docs/GOVERNANCE_CLOSURE.md`. | Smoke validates task-board warnings, risk blocking, quality gate authorization, merge queue processing, and active resource locks. |

## Closure Contract

The promoted process contract has three gates:

- execution closure: a worker ran, or the run is explicitly governance-only;
- evidence closure: reviewer evidence, tests, quality gates, and run JSON agree;
- integration closure: the merge queue is processable and final gate
  authorization is recorded.

Until all three are true, the kit must not claim merge, release, deploy,
provider-probe, data-refresh, cache-mutation, or durable-state readiness.

