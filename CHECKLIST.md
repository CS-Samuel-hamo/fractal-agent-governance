# CLI-First Runtime Checklist

## Before Running

- [ ] `agent bootstrap` has initialized `.zoo-agent/runtime-v4.json`.
- [ ] `AGENTS.md` and `.zoo-agent/code-standards.json` exist, or proposals are pending review.
- [ ] `agent map check` has no generated/runtime path blockers.
- [ ] Active goal exists under `.zoo-agent/goals/`.
- [ ] `.zoo-agent/loop_state.json` exists and is not diverging.
- [ ] Codex CLI is installed when execution is required: `codex --version`.
- [ ] `CODEX_HOME` points outside business project source.

## Runtime

- [ ] Use `agent run <input>` as the default entrypoint.
- [ ] Use `agent run --fast <input>` only for safe bounded work.
- [ ] Use `agent run --parallel <input>` only after independence and conflict-key checks pass.
- [ ] Use `agent run --governed <input>` for complex or risky work.
- [ ] Use `agent status --run-id <run-id>` before claiming run state.
- [ ] Use `agent rollback --run-id <run-id> --task-id <task-id> --dry-run` before discarding failed work.
- [ ] Use `agent reroute --run-id <run-id> --task-id <task-id> --path <path>` when classification was wrong.
- [ ] Use `agent review --run-id <run-id>` before merge-readiness claims.
- [ ] Do not require Zoo Code UI to control execution.
- [ ] Do not require user-supplied task ids on the default path.

## Evidence

- [ ] `.zoo-agent/runs/<run-id>/cli-runtime/<task-id>.json` exists.
- [ ] Goal alignment evidence exists and is not blocked.
- [ ] Scope guard and relevant tests are recorded before completion claims.
- [ ] Parallel workers use separate worktrees and output paths.
- [ ] Governed work has implementation queue, parent aggregation, merge queue evidence, and GPT review evidence.
- [ ] Rollback evidence stays under `.zoo-agent/runs/<run-id>/rollback/`.
- [ ] Reroute evidence stays under `.zoo-agent/runs/<run-id>/route-audit/`.
- [ ] Metrics exist under `.zoo-agent/metrics/agent-runtime-v4.json`.

