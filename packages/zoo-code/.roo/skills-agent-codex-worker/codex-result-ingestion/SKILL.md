---
name: codex-result-ingestion
description: Collect Codex CLI worker output and convert it into Zoo result artifacts.
version: 0.3.9
scope: governance
applies_to: agent-executor
last_updated: 2026-06-01
deprecated_by:
---

# Codex Result Ingestion

Use this skill after a Codex worker run completes or when a manually produced Codex result needs to be captured.

Steps:

1. Collect git status, diff names, diff stat, final message, progress, blockers, and run metadata.
2. Run the Codex scope guard.
3. Write `result.json` and `result.md`.
4. Update artifact graph.
5. Return evidence to Zoo review. Do not merge.
