# Architecture Feedback Hardening

Version: `0.3.11-governance-closure-codex-parallel`

This layer captures lessons from real business-project usage of older global
and governance kits. It does not replace the project bootstrapper. It wraps
bootstrap with compatibility checks that prevent stale or lower-confidence
runtime facts from silently becoming active architecture.

The generalized promotion map is in
`docs/FIELD_FEEDBACK_INTEGRATION_MATRIX.md`. Business-specific findings remain
local evidence; only reusable architecture and process lessons are promoted.

`0.3.11` also hardens Windows command probes. If `codex` or `npm` resolves to a
PowerShell/CMD shim, the probe retries `.cmd`, `.exe`, and `.bat` variants before
marking worker readiness as blocked. Terminal JSON output is ASCII-safe so
Chinese project paths do not turn a completed bootstrap into a console encoding
failure.

## Problems It Guards

- A refreshed project profile must not downgrade an existing high-confidence
  profile, such as losing `frontend/src`, Next.js, React, API routes, or known
  test commands.
- Project maps must not treat generated or runtime files as source roots,
  module owners, or API entrypoints.
- Codex worker readiness must not be assumed when `codex` is unavailable or
  `.zoo-agent/project-readiness.json` says Level 0/1 trials are unsafe.
- Dirty retired governance paths, generated data paths, and suspicious root
  artifacts must remain outside task attribution until a cleanup or migration
  contract exists.
- Record-only merge queues must stay visibly non-processable until a final
  reviewer or integration gate authorizes queue processing and merge readiness.
- Task-board consistency warnings, such as stale redirect plans, must be carried
  into continuation decisions.
- Test and readiness evidence must carry an environment fingerprint, especially
  Node ABI and native dependency load status for SQLite/Graph DB claims.
- Projects with both `.steward` and `.zoo-agent` need a source-of-truth resolver
  before durable state reconciliation.
- Dirty governance/runtime paths, retired governance framework paths, data/output
  artifacts, and task-board consistency warnings need path-scoped attribution
  before a worker resumes stale plans or broad integration.
- Governance-kit upgrades need a migration report and rollback anchor, not only
  copied commands.

## Bootstrap Artifacts

`scripts/agent_bootstrap.py` now writes these artifacts after the normal
bootstrap and entrypoint repair steps:

- `.zoo-agent/architecture-compatibility-report.json`
- `.zoo-agent/architecture-compatibility-report.md`
- `.zoo-agent/installed-kit-version.json`
- `.zoo-agent/bootstrap/scan-policy.json`
- `.zoo-agent/bootstrap/source-of-truth-resolver.json`
- `.zoo-agent/bootstrap/migration-report.md`
- `.zoo-agent/bootstrap/rollback-anchor.md`

The wrapper can finish with `ready_with_architecture_blocks`. That means the
entrypoints were installed, but architecture claims such as refreshed profile,
project map, Graph DB readiness, or native SQLite evidence must not be trusted
until the report is resolved.

## Source Of Truth Rule

For active execution, prefer current `.zoo-agent` runtime facts. For release
boundaries, prefer current release and product-definition docs. Treat
`.steward` and archived docs as existing state or historical evidence unless a
separate migration contract authorizes reconciliation.

When a project-level `AGENTS.md` says `docs/agent-governance/**` is historical
branch or integration evidence, the resolver records that role and keeps
`.zoo-agent/**` as the active runtime source. Retired `.antigravity/**` paths are
never restored, deleted, staged, or used for new work without a separate
migration or cleanup contract.

## Run Summary Rule

`scripts/summarize_ai_native_run.py` must summarize more than dispatcher and
Codex worker artifacts. It also reports:

- `.zoo-agent/project-readiness.json`
- `.zoo-agent/runs/<run-id>/status.json`
- `.zoo-agent/runs/<run-id>/merge-queue.json`
- `.zoo-agent/runs/<run-id>/parent-aggregation.json`
- `.zoo-agent/runs/<run-id>/risk-register.json`
- `.zoo-agent/runs/<run-id>/task-board-consistency.json`
- `.zoo-agent/runs/<run-id>/quality-gate.json`
- `.zoo-agent/runs/<run-id>/merge-queue-processing.json`
- `.zoo-agent/locks/resource-locks.json`

This prevents a run with reviewer evidence from being mistaken for merge,
deploy, release, or queue-processing approval.

## Native Dependency Rule

When a project has `frontend/package.json`, bootstrap probes:

- `node -v`
- `process.versions.modules`
- `npm -v`
- `better-sqlite3` package version and load status, when declared or installed

If `better-sqlite3` cannot load, Graph DB/SQLite readiness is conditional even
if previous evidence said the tests passed.

`scripts/collect_codex_result.py` records the same environment fingerprint in
each `codex-results/<task-id>/result.json` and `result.md`, so task evidence can
be compared against the runtime that actually produced it.
