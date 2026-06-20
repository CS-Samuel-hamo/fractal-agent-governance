# Goal-driven Execution Orchestrator 0.6.0

Agent Runtime 0.6.0 closes the big-task loop around the active goal:

```text
/goal
  -> Big Task Readiness Gate
  -> Decomposition Engine
  -> Leaf Task Contracts
  -> Leaf Convergence Controller
  -> Leaf Execution through Codex CLI
  -> Delivery Outcome + Scope Guard
  -> Parent Aggregation Gate
  -> Integration Worktree Candidate
  -> Goal Completion Check
  -> Next Goal Suggestion
```

## Runtime Roles

- CLI Runtime owns orchestration, routing, goal state, loop state, aggregation, and integration policy.
- Codex CLI is only a bounded leaf execution backend for patch generation and test execution.
- Codex CLI does not plan goals, decompose big tasks, aggregate leaf evidence, or decide integration.
- GPT/human decision is required for high-risk, blocked, diverging, or ambiguous states.

## Goal State

`goal_state.json` records:

- `goal_id`
- `status`: `active`, `converged`, `blocked`, `degraded`, or `completed`
- `progress_score`
- completed, remaining, and failed leaf counts
- loop iteration and maximum iterations
- drift detection
- optional next goal candidates

Goal completion is determined by parent aggregation evidence, not by leaf execution alone.

## Loop Control

Each parent aggregation advances the goal loop once. The loop stops or escalates when:

- parent aggregation satisfies all success criteria
- decomposition or leaf redo exceeds configured bounds
- backend/readiness/dependency failures block progress
- leaf completion does not improve goal coverage
- drift or over-decomposition is detected

The loop controller is a convergence and loss-control layer. It is not a planner and must not generate product documents as a substitute for execution evidence.

## Next Goal Suggestion

When a goal is completed, or when the loop is blocked/diverging, the runtime may write `next-goal-candidates.json`.

These candidates are suggestions only:

- no automatic execution
- no automatic goal replacement
- no merge or push

## Safety Boundary

- No task may execute without a goal binding.
- Big tasks without an explicit goal are blocked.
- Fast path may use lightweight transient goals only for simple small tasks.
- Leaf completion contributes to goal progress only through delivery outcome and parent aggregation coverage.
- `no_delivery` never counts as goal progress.
