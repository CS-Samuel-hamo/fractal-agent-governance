# Human Exception Policy

Human exception records require:
- `exception_id`
- `approver`
- `scope`
- `reason`
- `accepted_risk`
- `rollback_plan`
- `monitoring_plan`
- `expiry`

DeepSeek cannot accept, close, or rely on a human exception as final authority. Security, auth, payment, PII, credentials, production config, database migration, destructive operation, and external network access require explicit high-risk approval and cannot be bypassed by an ordinary exception.
