---
description: Review a Codex worker result before Zoo integration.
argument-hint: <run-id> <task-id>
mode: agent-reviewer
---

Review Codex result for `$ARGUMENTS`.

Check scope guard, changed files, acceptance evidence, test output, blocker notes, and whether Codex inferred architecture, public API, security, or dependency changes without approval. Produce APPROVE, APPROVE_WITH_MINOR_FIXES, REQUEST_CHANGES, or REDESIGN_REQUIRED.
