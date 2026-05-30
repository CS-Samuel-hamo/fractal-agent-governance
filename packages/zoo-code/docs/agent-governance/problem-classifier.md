# Problem Classifier

Classify blockers before choosing escalation or fallback.

| Signal | Problem Class | Next State |
| --- | --- | --- |
| requirement conflict | product ambiguity | escalation: requirement_conflict |
| architecture boundary unknown | architecture ambiguity | GPT planner/architect |
| Proc/Processor source mismatch | data semantics ambiguity | escalation: data_source_unknown |
| test command unknown | verification ambiguity | escalation: test_strategy_unknown |
| security/auth/payment/PII | high-risk governance | stop + human/GPT gate |
| required obligation open | implicit work gap | executor or escalation: obligation_unresolved |
| two stalled loops | convergence failure | escalation then fallback ladder |
| depth exceeds max | decomposition failure | GPT branch-manager |
