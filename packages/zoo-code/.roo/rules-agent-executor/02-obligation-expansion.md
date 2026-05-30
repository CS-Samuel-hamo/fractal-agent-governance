# Executor Obligation Expansion

Before coding, executor must transform the explicit request into `.zoo-agent/runs/<run-id>/obligation-ledger.json`. Classify each obligation as required, maybe, not_applicable, deferred, required_but_blocked, or escalated. Do not mark not_applicable without evidence. Do not implement only literal code while leaving propagation obligations unresolved.

Search existing patterns before new types/utilities/handlers/processors. Stop and escalate for unclear obligation, conflicting patterns, data-source mismatch, architecture unknown, security/auth/PII/payment/migration, or unknown test strategy. Completion Evidence must reference the obligation ledger.
