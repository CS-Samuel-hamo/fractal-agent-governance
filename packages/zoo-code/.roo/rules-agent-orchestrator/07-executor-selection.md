# Executor Selection

The orchestrator selects an executor after governance intensity classification.

Use `scripts/classify-task-complexity.py` and `scripts/select-executor.py` when local artifacts are available. The selection file is `.zoo-agent/runs/<run-id>/executor-selection.json`.

Rules:

- Level 0: fast path, optional Codex CLI or DeepSeek.
- Level 1: Codex CLI preferred unless DeepSeek is explicitly selected for low-risk drafting or mechanical review.
- Level 2: GPT planner approval before Codex CLI.
- Level 3: Zoo decomposes, then Codex executes leaf tasks.
- Level 4: GPT/human gate; Codex executes only approved bounded subtasks.

If selection is ambiguous, route upward and record blocking factors.
