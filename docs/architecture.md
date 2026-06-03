# Architecture

Fractal Agent Governance Runtime adds an explicit governance layer around AI coding agent execution.

Core flow:

1. A goal starts a run.
2. Project bootstrap creates or refreshes project facts.
3. `current-run.json` points to the active run.
4. `.zoo-agent/TASKS.md` is the human-editable project task-board entry.
5. The project profile describes local constraints and surfaces.
6. The obligation ledger captures explicit and implicit work.
7. The fractal branch tree decomposes complex work under depth and ownership controls.
8. GPT decision layers handle planning, review, escalation, parallel approval, and aggregation.
9. Codex or DeepSeek execution layers handle bounded implementation tasks.
10. Quality, review, and integration gates check evidence before completion.
11. Worktree runtime isolates parallel exploration.
12. Path locks and resource locks prevent unsafe parallelism.
13. Merge queue serializes integration.
14. Learning loop feeds outcomes back into future governance decisions.

See `media/architecture.mmd` for the diagram source.

The package deliberately separates durable facts from human controls:

- Machine facts: JSON artifacts under `.zoo-agent/`.
- Human controls: `TASKS.md`, branch task documents, reports, and `.new` / `.patch` proposals.
- Execution isolation: Codex task packs and Git worktrees for bounded leaf work.
