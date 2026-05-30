# Generalized Implicit Work Discovery

Implicit work discovery converts a literal request into the obligations required to deliver a coherent software change. It compensates for models that tend to satisfy only the words in the request.

## Required Flow

1. Capture the explicit user request.
2. Classify task type: feature, behavior change, bug fix, field/schema change, integration, refactor, migration, security, release, or operational change.
3. Scan impact surfaces using the taxonomy.
4. Search existing patterns before creating new types, handlers, processors, or utilities.
5. Generate `.zoo-agent/runs/<run-id>/obligation-ledger.json`.
6. Mark each obligation as `required`, `maybe`, `required_but_blocked`, `not_applicable`, `deferred`, or `escalated`.
7. Block coding when required obligations are unknown, security-sensitive, architecture-sensitive, or have no verification path.

## Executable Examples

If the user asks to add a field, infer DTO/schema, mapper, storage/migration, API response, validation, tests, and public docs/release note when the field is externally visible.

If the user asks to change behavior, infer affected callers, backward compatibility, tests, error behavior, and observability when failures need diagnosis.

If the user asks to use an existing Proc or Processor, infer existing pattern search, data-source semantics, adapter/source-selector need, old/new behavior tests, and escalation when data source mismatch is unknown.

## Stop Conditions

Stop and escalate when obligations are unclear, existing patterns conflict, data-source semantics differ, architecture boundary is unknown, security/auth/PII/payment/migration is involved, or required test strategy is unknown.
