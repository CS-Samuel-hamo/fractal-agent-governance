# Codex CLI Worker Bridge

The Codex CLI Worker Bridge converts a Zoo branch or task into a bounded Codex Task Pack and then collects Codex evidence back into Zoo.

## Bridge Steps

1. Select or create a run id and task id.
2. Classify task complexity and governance intensity.
3. Select executor.
4. Generate a Codex Task Pack under `.zoo-agent/runs/<run-id>/codex-tasks/<task-id>/`.
5. Run Codex CLI only when user or automation policy allows it.
6. Collect stdout, stderr, exit code, final message, progress, blockers, scope report, and git evidence.
7. Write `.zoo-agent/runs/<run-id>/codex-results/<task-id>/result.json`.
8. Write `.zoo-agent/runs/<run-id>/codex-results/<task-id>/result.md`.
9. Update artifact graph.
10. Return to Zoo quality gate, review gate, and merge queue.

Codex CLI is a worker. Zoo owns final review, integration, and merge decisions.
