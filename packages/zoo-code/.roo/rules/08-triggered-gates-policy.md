# Triggered Gates Policy

ADR, security, release, ops, eval, and curator gates are triggered gates. They do not run by default for every task.

ADR triggers:
- public API
- shared type
- new dependency
- architecture boundary change
- migration
- Proc/data-source strategy

Security triggers:
- auth
- permission
- PII
- payment
- credential
- external network
- production config

Release triggers:
- public behavior change
- migration
- feature flag
- breaking change

Ops triggers:
- backend/API/job/database/integration
- retry, idempotency, logging, metrics, alerting

Curator triggers:
- repeated failure
- BLOCKER or MAJOR review finding
- same failure type recurrence
- rule or skill drift

Eval triggers:
- governance package upgrade
- new skill or rule
- model routing change
- benchmark or demo

If a trigger exists, the corresponding gate must be recorded in the run artifacts. If no trigger exists, record `not_triggered` rather than running ceremony by habit.
