# Implementation Delivery Kernel

Version: 0.3.9.3-implementation-delivery-kernel

The Implementation Delivery Kernel closes the gap between governance planning
and actual code delivery. Product documents remain important inputs, but coding
tasks must terminate into implementation queue items, Codex task packs, code or
test diffs, scope guard evidence, and reviewable delivery gates.

## Principles

- Product docs are inputs, not the default output of coding tasks.
- Planning must terminate into executable leaf tasks.
- Coding tasks must produce code, test, config, or execution evidence unless
  explicitly classified as non-coding.
- Local optimization must not block root-goal delivery.
- Codex Worker is the preferred execution path for bounded Level 0/1/2
  implementation leaf tasks.
- Zoo remains the governance and control plane; Codex performs bounded
  execution; GPT makes final delivery decisions; lower-cost models may assist
  with drafting and classification.

## Delivery Loop

1. Bind the current task to a root goal and acceptance criteria.
2. Classify delivery mode: coding, docs-only, research, planning, review, or
   blocked.
3. Generate or refresh the implementation queue.
4. Promote ready executable queue items to Codex task packs.
5. Run bounded workers only when authorized.
6. Collect worker results, scope guard, and tests.
7. Run the code delivery gate.
8. Review root-goal delivery, local optimization, and doc-only drift before
   parent aggregation or merge queue entry.

## Non-Goals

This kernel does not authorize merge, push, deploy, release, destructive
cleanup, worktree deletion, production data migration, secret reads, or business
repository code changes during global kit installation.
