# AI-Native Governance Principles

Zoo governance is not a copy of a human software company's approval chain. AI coding changes the cost structure:

- Code generation and sandbox experimentation are cheap.
- Verification, integration judgment, architecture drift, security/data mistakes, release risk, and long-term maintenance remain expensive.
- Governance must therefore route effort by risk, coupling, reversibility, and feedback speed rather than applying full ceremony to every change.

## Principles

1. Classify before governing.
   Every `/agent-run` must classify governance intensity before choosing gates. Do not default to full governance.

2. Keep the mainline narrow.
   Exploration may be parallel in sandbox or Git worktrees. Integration into the mainline is serialized through gates, parent aggregation, and merge queue.

3. Evidence is proportional to risk.
   Level 0 needs a diff summary and optional check. Level 4 needs ADR, security/release readiness, rollback, and human gate where required.

4. Trigger expensive gates.
   ADR, security, release, ops, eval, and curator flows run only when triggers are present. They are not default steps for every task.

5. Do not confuse cheap code with cheap integration.
   A generated patch is not ready because it compiles locally. Shared interfaces, data semantics, auth, migration, and public behavior still require stronger gates.

6. Prefer reversible feedback loops.
   Use targeted tests, quick checks, worktree experiments, and rollback plans to keep iteration cheap. Stop or escalate when feedback stalls or regresses.

7. Reserve full governance for high-risk work.
   Full goal/fractal/release/security/human-gate flow is mandatory for Level 4 and selectively used for Level 3. It is wasteful for micro edits.

## Runtime Placement

The AI-native layer sits immediately after project profile discovery:

`Project Context -> Governance Intensity -> Triggered Gates -> Appropriate Execution Path`

The runtime backbone still owns run_id, artifact graph, state transitions, metrics, and lesson capture. Adaptive governance decides how much of that backbone is activated.
