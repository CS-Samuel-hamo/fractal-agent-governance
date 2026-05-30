# Impact Surface Taxonomy

Use this taxonomy when expanding implicit work.

## Code Interface Surfaces
public API, internal interface, function signature, type/DTO/schema, enum/constant, exports/barrel files.

## Invocation / Wiring Surfaces
route, command, task branch, dispatcher, registry, factory, provider, dependency injection, event handler, job queue, scheduler.

## Domain / Data Surfaces
domain model, repository, mapper, validator, persistence schema, migration, fixture, seed data, cache, Proc/Processor, data source semantics.

## Behavior / Compatibility Surfaces
backward compatibility, API versioning, feature flag, error behavior, retry/idempotency, concurrency, permissions, user-facing behavior.

## Verification Surfaces
unit tests, integration tests, API request/response tests, negative tests, migration tests, fixture update, snapshot/golden tests, smoke tests.

## Operational Surfaces
config, env var declaration, logging, metrics, tracing, alerting, runbook, rollback plan, release note.

## Documentation / Governance Surfaces
README, docs, decision record, branch-state, task contract, release note, migration guide.
