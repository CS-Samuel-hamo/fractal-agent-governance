# Implicit Work Discovery Policy

For every non-trivial coding task, convert the explicit request into an Obligation Ledger before implementation. The ledger must cover impact surfaces, required propagation work, verification obligations, compatibility obligations, operational obligations, documentation obligations, and rollback obligations.

Required obligations cannot remain open at integration. `not_applicable` requires evidence. `deferred` requires owner and reason. `escalated` requires escalation id. DeepSeek may draft the ledger but cannot approve its own coverage.
