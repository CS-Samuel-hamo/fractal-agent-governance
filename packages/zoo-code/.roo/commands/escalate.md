---
description: Create an escalation record when automation cannot safely converge.
argument-hint: <reason>
mode: agent-orchestrator
---

Generate `.zoo-agent/escalations/<escalation-id>.json`. Valid reasons include requirement_conflict, architecture_unknown, data_source_unknown, test_strategy_unknown, security_or_auth_risk, migration_risk, quality_gate_repeated_fail, review_loop_exhausted, decomposition_depth_exceeded, dependency_blocked, obligation_unresolved, cost_budget_exceeded, human_decision_required. DeepSeek cannot close escalation.
