# CLI-First Agent Entrypoints

- Use `agent bootstrap` once per project to initialize CLI runtime state.
- Use `agent run <input>` as the normal execution entrypoint.
- Use `agent run --fast <input>` only when forcing the fast path is safe.
- Use `agent run --parallel <input>` only when independent tasks have disjoint conflict keys and no shared schema/API/DB/output surfaces.
- Use `agent run --governed <input>` for complex work requiring decomposition, reconciliation, parent aggregation, merge queue evidence, and GPT review.
- Use `agent status --run-id <run-id>` for run-state inspection.
- Use `agent rollback --run-id <run-id> --task-id <task-id> --dry-run` before discarding failed work.
- Use `agent reroute --run-id <run-id> --task-id <task-id> --path <path>` when classification was wrong.
- Use `agent map check` before trusting active project-map claims.
- Use `agent review --run-id <run-id>` before merge-readiness claims.
- The CLI runtime owns goal, loop, classification, metrics, status, rollback, review, and execution control.
- Codex CLI is the execution backend; it does not own planning or orchestration.
- Zoo Code is an optional UI layer and should delegate to the same CLI runtime.
- Every task must bind to a `goal_id` and produce goal-alignment evidence.
- The runtime must write `.zoo-agent/loop_state.json`; when iteration exceeds `max_iteration`, route to governed/GPT decision-layer review.
- Treat `.zoo-agent/runs/<run-id>/cli-runtime/<task-id>.json` and `.zoo-agent/metrics/agent-runtime-v4.json` as primary runtime evidence.
- Treat planner, orchestrator, reviewer, and integrator as governed-path responsibilities, not extra runtime entrypoints.

