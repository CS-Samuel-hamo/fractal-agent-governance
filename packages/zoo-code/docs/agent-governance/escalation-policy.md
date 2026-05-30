# Escalation Policy

`/escalate` creates `.zoo-agent/escalations/<escalation-id>.json`. DeepSeek may draft escalation evidence but cannot close escalation.

Valid reasons:
- requirement_conflict
- architecture_unknown
- data_source_unknown
- test_strategy_unknown
- security_or_auth_risk
- migration_risk
- quality_gate_repeated_fail
- review_loop_exhausted
- decomposition_depth_exceeded
- dependency_blocked
- obligation_unresolved
- cost_budget_exceeded
- human_decision_required

GPT or human authority must decide the next state. Escalation cannot be resolved by local branch optimization.
