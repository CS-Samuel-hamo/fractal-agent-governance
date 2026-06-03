# Automated Orchestration Model

The standard workflow is intended to be executed by `agent-orchestrator`, not manually step-by-step.

## What Zoo Code can automate

- Delegate subtasks to specialist modes through Boomerang Tasks / `new_task`.
- Preserve parent-child task hierarchy.
- Pass child summaries back to the parent task.
- Switch modes or create/complete subtasks automatically if Auto-Approve permissions are enabled.
- Load mode-specific rules and skills when the selected mode runs.
- Create checkpoints during active Zoo Code tasks before file modifications.

## What remains a control boundary

- User approval is required by default for mode switches, new subtasks, file edits, and commands unless Auto-Approve is explicitly enabled.
- Worktree creation is usually an operator or UI boundary. Treat it as a controlled phase gate for non-trivial tasks.
- Child tasks do not automatically inherit full parent context. The orchestrator must pass the contract and required context down explicitly.
- API profiles may be sticky per task. Verify model/profile routing when mixing GPT planning/review and DeepSeek execution.
- Integration/merge remains a release-quality gate. Do not auto-merge BLOCKER or MAJOR review outcomes.

## Recommended operating modes

### Semi-automatic, recommended

Auto-approve only low-risk orchestration actions:

```text
Read files: optional
Switch modes: on
Create & complete subtasks: on
Edit files: off or manual
Execute commands: approved allowlist only
MCP/browser: off unless needed
```

### High-autonomy, only in disposable worktrees

Enable edits and approved commands only inside isolated worktrees with checkpoints on and no production secrets copied into the worktree.

## Entry point

Use:

```text
/agent-run <requirement>
```

This starts in `agent-orchestrator`, which delegates the planner, executor, reviewer, and integrator phases as needed. Branch management and governance curation are internal capabilities of planner and integrator, not separate visible modes.
