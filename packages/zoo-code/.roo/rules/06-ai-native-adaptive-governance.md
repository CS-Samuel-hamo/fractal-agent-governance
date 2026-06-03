# AI-Native Adaptive Governance

Do not copy human software team ceremony step-for-step. AI lowers the cost of patch generation and sandbox exploration, but it does not lower the cost of wrong integration, architecture drift, security/data exposure, migration damage, or long-term maintenance.

Mandatory behavior:

1. Classify governance intensity before selecting gates.
2. Use the lightest level that safely covers the task.
3. Keep low-risk Level 0/1 tasks fast.
4. Use full governance only when risk, coupling, irreversibility, unknowns, or public/shared surface impact require it.
5. Allow parallel exploration only in sandbox/worktree isolation.
6. Never allow parallel direct integration.
7. Preserve runtime backbone IDs and artifacts for any task that enters planning, execution, review, aggregation, integration, metrics, or lessons.
8. Treat Stop and Redirect as steering mechanisms. Existing useful artifacts should be retained, and replanning should be minimal and evidence-based.
9. The active child branch must remain visible in its parent/root context through progress snapshots or GUI tree.
10. After Stop, Redirect, or Apply Task Board, run resume safety before continuing execution.
11. Use codebase indexing when available for obligation discovery, existing pattern mining, branch decomposition, and semantic resource lock generation; fallback to `rg`/file search and record the discovery method.

Cheap code generation is not evidence of safe integration. Shared interfaces, auth, data semantics, migrations, production config, and public behavior require triggered gates.
