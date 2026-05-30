# Governance Intensity Routing

Every `/agent-run` must run governance intensity routing after project profile discovery and before coding.

Levels:

- Level 0 Micro Edit: comments, tiny docs, formatting, no behavior change. Require high-risk path guard, diff summary, optional test. Do not require full goal, fractal decomposition, or full review.
- Level 1 Routine Coding: small bugfix or small feature using existing patterns. Require mini obligation check, targeted test, mechanical review.
- Level 2 Multi-surface Feature: API, service, DTO, schema, registry, provider, tests, or more than one propagation surface. Require goal-lite, full obligation ledger, GPT planner approval, quality gate, GPT reviewer.
- Level 3 Fractal Workstream: multiple boundaries, multiple risks, more than 8 projected files, unknowns, Proc/data-source mismatch, or research-before-implementation. Require root branch, fractal decomposition, parent aggregation, integration gate.
- Level 4 High-risk / Irreversible Change: auth, payment, PII, migration, security, production config, destructive operation, or breaking public API. Require full governance, ADR/security/release gates, rollback plan, and human gate where required.

If classification is uncertain, route to the higher level and record the uncertainty in `governance-intensity.json`.

DeepSeek may draft classification evidence. GPT decides Level 3/4 routing and any escalation from lower levels when ambiguity exists.
