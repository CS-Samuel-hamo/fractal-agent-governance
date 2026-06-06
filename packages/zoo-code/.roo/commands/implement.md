---
description: Convert current plan/branch/task board into executable implementation queue and Codex task packs.
argument-hint: [optional run_id or branch_id]
mode: agent-orchestrator
---

# Implement

Use this command when a plan, task board, or branch tree must become executable
work instead of more product documentation.

## Flow

1. Detect current run id from `$ARGUMENTS`, `.zoo-agent/current-run.json`, or the
   latest `.zoo-agent/runs/<run-id>` folder.
2. Read goal, task board, branch state, obligation ledger, and project profile
   when present.
3. Run `scripts/generate-implementation-queue.py`.
4. Run `scripts/check-implementation-queue.py`.
5. Promote ready `code` or `test` items to Codex task packs with
   `scripts/promote-leaf-tasks-to-codex.py`.
6. Do not write product docs unless the item is explicitly docs-only.
7. If the user explicitly authorizes worker execution, run bounded Codex worker;
   otherwise stop after task-pack generation and print the resume command.

## Implementation Plan

Produce:

- Ready for Code
- Ready for Tests
- Blocked
- Follow-up / Local Optimization
- Codex Task Packs
- Next Command
