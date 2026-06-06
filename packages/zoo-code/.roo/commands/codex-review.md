# Codex Review

Review a dispatcher or worker result before merge.

Start from:

- `.zoo-agent/runs/<run-id>/ai-native-summary.json`
- `.zoo-agent/runs/<run-id>/dispatcher-runs/<task-id>.json`
- `.zoo-agent/runs/<run-id>/optimistic-runs/<task-id>.json`
- `.zoo-agent/runs/<run-id>/codex-results/<task-id>/result.json`

Review order:

1. Confirm scope guard status.
2. Confirm tests were run or explicitly deferred.
3. Inspect changed files.
4. Inspect worker final message and blockers.
5. For Level 3, confirm every leaf has its own verification evidence.

Do not merge automatically. Produce a merge-candidate recommendation only.

For Implementation Delivery Kernel runs, also inspect:

- `.zoo-agent/runs/<run-id>/implementation-queue.json`
- `.zoo-agent/runs/<run-id>/code-delivery-gate.json`
- `implementation_item_id` in Codex result metadata

Reject coding branches that only produced product docs unless they are explicitly
classified as docs-only or blocked with a precise next action.
