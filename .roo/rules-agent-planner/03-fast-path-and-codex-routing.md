# Fast Path And CLI Routing

The default route is fast when coupling, uncertainty, blast radius, and
dependency risk are low.

- Do not create a planning loop for fast-path work.
- Do not decompose, split tasks, or expand product docs on the fast path.
- Fast path maps to Codex CLI execution through the bounded backend, followed
  by scope guard, tests, and result collection.
- Parallel path is allowed only for independent tasks with non-overlapping
  conflict keys and separate worktrees/output paths.
- Governed path is for complex or risky work and must end in GPT
  decision-layer review.
- Treat Codex CLI as code executor, test runner through harness, and patch
  generator. Do not treat Codex CLI as planner or orchestrator.

