# Closed-Loop Runtime

Every `/agent-run` must create a `run_id`, `run-ledger.json`, and `artifact-graph.json`.

No run ledger: no coding. No artifact graph: no review. No quality gate: no integration. No event ID: no governance rule/skill change. Human exception cannot bypass security, auth, payment, PII, secret, or destructive-operation gates.

Each phase records input artifacts, output artifacts, owner mode, model, gate status, and next allowed states. Orchestrator advances from ledger state, not scattered context.
