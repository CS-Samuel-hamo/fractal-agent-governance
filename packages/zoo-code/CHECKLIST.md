# Execution Checklist

## Before Running

- [ ] Codex CLI is installed: `codex --version`
- [ ] Codex CLI is authenticated: `codex login`
- [ ] `CODEX_HOME` points to the intended local state directory.
- [ ] The governance kit path is known, for example `$env:USERPROFILE\.roo\agent-governance-kit`.
- [ ] The target project has been set up with `setup_zoo_agent.py` or `agent-setup`.
- [ ] The integrated board can be rendered with `agent-board` or `render_governance_board.py`.

## During Execution

- [ ] `agent-run` or `run_ai_native_task.py` created a task context envelope.
- [ ] Durable project state is read-only unless a durable update was explicitly requested.
- [ ] Codex workers run only in bounded task packs or managed worktrees.
- [ ] Parallel workers have independent worktrees, output files, task packs, and resource locks.
- [ ] Tests, scope guard, result collection, and quality gate evidence are recorded outside the worker.

## Before Claiming Completion

- [ ] `.zoo-agent/BOARD.md` has been refreshed.
- [ ] `.zoo-agent/runs/<run-id>/task-board-consistency.json` has no unresolved warning that affects the claim.
- [ ] `.zoo-agent/runs/<run-id>/risk-register.json` has no unaccepted open risk.
- [ ] `.zoo-agent/runs/<run-id>/quality-gate.json` passes for the claimed outcome.
- [ ] Merge queue processing is explicitly authorized when integration is claimed.
- [ ] No deploy, release, provider probe, data update, cache mutation, or durable-state write is claimed without its own evidence.
