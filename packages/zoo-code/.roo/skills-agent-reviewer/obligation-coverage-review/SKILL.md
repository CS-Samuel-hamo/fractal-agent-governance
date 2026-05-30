---
name: obligation-coverage-review
description: Review whether implementation covers explicit and implicit obligations before final verdict.
version: 3.6.0
scope: global
applies_to: agent-reviewer
last_updated: 2026-05-30
deprecated_by: ""
---

Check obligation-ledger.json, changed files, tests, docs, release/operational readiness, and Completion Evidence. BLOCKER when required obligations remain open or verification obligations are unmapped.

For high-risk new shared utility/type, public API, Proc/Processor, registry/provider, or architecture boundary changes, verify semantic pattern discovery was attempted through Zoo Code codebase indexing when available or a documented fallback search. Missing `discovery_method` is at least MAJOR and may be BLOCKER when integration risk is high.
