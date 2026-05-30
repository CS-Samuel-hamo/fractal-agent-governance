# Delivery Management

Each run maintains `.zoo-agent/runs/<run-id>/status.json`. The status board records current state, active branch, completed branches, blocked branches, next allowed states, owner mode, blockers, risks, and required human actions.

Delivery management replaces manual status meetings with artifacts. The orchestrator advances only through allowed states in the run ledger and status board. Branch clerks may update status; GPT decides blocked/high-risk transitions.
