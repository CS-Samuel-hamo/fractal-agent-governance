# Fast Path And Codex Routing

Plan parent tasks only enough to choose an execution envelope.

- Do not add a separate short-term vs long-term classifier. Pass the user request plus durable project context into the dispatcher.
- Treat project charter, active goal, and task boards as background that guides decomposition and verification.
- If a task is bounded and reversible, route it to the dispatcher and let it attempt in an isolated worktree.
- If the parent task is broad, decompose it into bounded leaves.
- Prefer the generated Level 3 leaf skeletons as drafts, then refine only the broad or ambiguous leaves.
- Use each leaf's `execution_graph` to decide whether it is light enough to execute, can run in parallel, or must stay planned/gated.
- Leaves may run in parallel only when their `conflict_keys` do not overlap.
- Re-route each leaf independently; do not force the parent governance level onto every leaf.
- Prefer cheap evidence from tests, scope guard, and diff summaries over heavy pre-execution analysis.
- Use the parallel scheduler only after generated leaves pass the concurrency
  checker; blocked leaves must be refined, serialized, or escalated.
