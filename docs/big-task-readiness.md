# Big Task Readiness

Big Task Readiness decides whether a large request can be decomposed, dry-run at leaf level, or considered for explicitly confirmed low-risk leaf execution.

Inputs include the active goal, success criteria, non-goals, project readiness, backend profile, loop state, architecture knowledge, test capability, rollback capability, affected domains, and affected resources.

Missing goal blocks big task decomposition. Unknown test or rollback capability prevents leaf actual execution. Unhealthy backend prevents Codex actual execution. High or critical risk requires GPT/human gate.
