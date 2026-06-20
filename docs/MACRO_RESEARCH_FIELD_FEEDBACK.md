# Macro Research Field Feedback

Source project: `<PROJECT_ROOT>`

Reviewed date: 2026-06-03

## Business Contract Observed

The business app is a buy-side macro research desk, not a loose collection of
dashboards. Its current contract is one research path:

```text
Macro Chain -> Evidence -> Market Pricing -> Replay Lab
```

The same active macro issue key should travel through the four views. Direct
official evidence, market/proxy evidence, stale data, fallback data, and strict
audit gaps must remain visibly distinct. Medium-term daily proxy tape is allowed
for v1 research, but it must not be presented as direct market-implied
expectations or official macro fact.

## Architecture Fit

The product architecture is directionally aligned with the global governance
model:

- `.zoo-agent/**` is the active runtime and project-fact source.
- `docs/agent-governance/**` is historical branch and integration evidence.
- Product contracts are now expressed as charter, workflow, source-quality
  gates, risk register, merge queue, parent aggregation, and task-board state.
- Large work has been decomposed into P1/P2 leaves with scoped reviewer evidence.

The main mismatch is execution closure. The business project has strong
governance evidence, but the Codex worker loop was not actually ready because
`codex` was unavailable and `project-readiness.json` marked Level 0/1 trials as
unsafe.

Promotion note: the business workflow details above are project-local evidence.
The reusable lessons promoted into the kit are the source-of-truth rule,
readiness checks, dirty-path attribution, run-summary governance state, and the
three closure gates. See `docs/FIELD_FEEDBACK_INTEGRATION_MATRIX.md`.

## Problems Found

- Business docs drifted: `README.md`, `ARCHITECTURE.md`, `modules/README.md`,
  and `tabs/README.md` do not all describe the same file sizes and debt state.
- Run evidence drifted repeatedly: reviewer findings mention stale run-local
  artifacts, then integration hygiene refreshes them.
- Merge queue materialized as record-only, but not processable; it explicitly
  does not authorize merge, deploy, release, provider probes, data updates,
  cache mutation, or secret/provider-profile reads.
- The working tree contains product changes, governance changes, data-runtime
  files, deleted retired `.antigravity` paths, and suspicious root files such as
  `$null` and `3)])`; broad staging or rollback would be unsafe.
- Open run-level risks remain around secrets/provider profiles, data refresh
  scripts and provider probes, and financial proxy overclaim.
- The current active path points to P2 Leaf 4 integration hygiene; the next
  recommended phase is P2 Leaf 5 post-event review/archive closure, not parent
  aggregation or merge.

## Architecture Changes Made

- Bootstrap compatibility reports now flag missing Codex CLI, unsafe Level 0/1
  readiness, retired governance dirty paths, runtime data dirty paths,
  suspicious root artifacts, governance runtime dirty paths, and task-board
  consistency warnings.
- Source-of-truth resolver now records `.antigravity/**` as retired evidence and
  respects project `AGENTS.md` when `docs/agent-governance/**` is historical.
- Task contexts now include project readiness, architecture compatibility,
  source-of-truth resolver, and local rules summary as read-only runtime facts.
- AI-native summaries now include governance state from status, merge queue,
  parent aggregation, risk register, project readiness, and task-board
  consistency.

## Iteration Direction

The next architecture iteration should treat real business projects as stateful
systems with three closure gates:

- execution closure: Codex worker or fallback executor actually ran, or the run
  is explicitly governance-only.
- evidence closure: reviewer evidence, tests, quality gates, and run-local JSON
  agree.
- integration closure: merge queue is processable, path exclusions are resolved
  or carried, and final reviewer/integrator gate authorizes the next action.

Until all three are true, the architecture should avoid claiming merge,
release, deploy, data-refresh, or durable-state readiness.

