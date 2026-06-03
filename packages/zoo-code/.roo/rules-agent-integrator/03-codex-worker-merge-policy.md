# Codex Worker Merge Policy

Integrator must not merge Codex output directly from a worker result.

Required before integration:

- scope guard pass
- quality gate pass
- reviewer APPROVE or APPROVE_WITH_MINOR_FIXES
- parent aggregation pass for Level 3 work
- merge queue entry for parallel or branch work
- no unapproved denied file, architecture, public API, dependency, auth, security, PII, payment, schema, migration, or production config change

Codex CLI never decides final merge.
