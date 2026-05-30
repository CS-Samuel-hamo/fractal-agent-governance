---
description: Generate or update a run status summary without modifying business code.
argument-hint: <run-id>
mode: agent-branch-clerk
---

Use `.zoo-agent/runs/<run-id>/status.json` and run ledger evidence to summarize current state, active branch, completed branches, blocked branches, next allowed states, owner, blockers, risks, and required human actions. DeepSeek may draft; GPT resolves blocked/high-risk transitions.
