---
name: obligation-ledger-check
description: Mechanically verify obligation ledger presence, closure, deferral, escalation, and evidence references.
version: 3.6.0
scope: global
applies_to: agent-mechanical-reviewer
last_updated: 2026-05-30
deprecated_by: ""
---

Run or read `scripts/check-obligation-ledger.py`. Verify required obligations are closed, deferred items have owner/reason, escalated items have escalation id, and not_applicable items have evidence. Do not issue final merge verdict.
