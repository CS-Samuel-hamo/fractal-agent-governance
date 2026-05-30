# Adaptive Gate Policy

Adaptive gates replace default full ceremony with triggered, risk-based checks.

## Default Gates By Level

| Level | Default Gates |
| --- | --- |
| 0 | high-risk path guard, diff summary |
| 1 | mini obligation check, targeted test, mechanical review |
| 2 | full obligation ledger, GPT planner approval, quality gate, GPT reviewer |
| 3 | Level 2 gates plus branch contracts, fractal decomposition, parent aggregation, integration gate |
| 4 | Level 3 gates plus ADR, security/data gate, release readiness, explicit rollback, human gate when required |

## Triggered Gates

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
- backend/API/job/database/integration change
- retry/idempotency/logging/metrics/alerting change

Curator triggers:
- repeated failure
- BLOCKER or MAJOR finding
- same failure type recurrence
- rule or skill drift

Eval triggers:
- governance package upgrade
- new skill or rule
- model routing change
- benchmark/demo request

Eval is not part of every task. It measures the governance system itself.

## Gate Selection Rule

Run `scripts/check-triggered-gates.py` after intensity classification. A required gate may not be skipped because a lower-cost model produced a plausible patch. A triggered gate must record the signal that activated it.
