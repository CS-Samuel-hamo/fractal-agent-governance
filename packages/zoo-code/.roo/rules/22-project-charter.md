# Project Charter

The project charter is the durable project constitution. It lives at `.zoo-agent/project-charter.json` with a human-readable sibling at `docs/project-charter.md`.

Do not use `TASKS.md` as the project constitution. `TASKS.md` is only the current run's editable task board.

Before non-trivial coding:

1. Ensure a project charter exists or record `charter_unknown`.
2. Ensure the goal contract aligns with mission, non-goals, success criteria, quality bar, data/security constraints, human gates, and fallback/abort conditions.
3. Stop for GPT planner or user decision when the requested goal conflicts with the charter.
4. Do not invent missing charter facts. Unknown material fields remain `unknown` and block high-risk or multi-module work.

The charter may be drafted during first-run intake. It must not contain secrets, API keys, customer private data, or current branch execution status.
