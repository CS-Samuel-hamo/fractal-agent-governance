# Multi-goal Execution Runtime 0.7.0

Agent Runtime 0.7.0 extends the 0.6 single-goal execution loop into a goal-set runtime.

## Architecture

```text
User
  -> Goal Set
  -> Global Loop Engine
  -> Goal Scheduler
  -> Active Goal
  -> Big Task System
  -> Leaf Convergence System
  -> Codex Execution Backend
  -> Parent Aggregation
  -> Goal Update
  -> Scheduler Rebalance
```

Only one goal is active by default. Other goals are paused or kept in backlog until the scheduler selects them.

## State

The canonical multi-goal state is:

```text
.zoo-agent/goal/goal_state.json
```

It contains:

- `goals[]`: goal records with status, priority, progress, resources, dependencies, and starvation counters.
- `global_loop_state`: system-level iteration, active goal, backend health, system status, paused/backlog/completed goals, and execution freeze state.

The legacy compatibility path remains:

```text
.zoo-agent/goal_state.json
```

It mirrors the same multi-goal state for older scripts.

## Goal Scheduling

`scripts/goal_scheduler.py` applies:

- priority-based ranking
- dependency blocking
- max continuous active iterations
- starvation prevention through starvation counters
- single active goal by default
- backend unhealthy freeze

Low-priority goals are not allowed to stay frozen forever. Starvation count gradually boosts scheduling score.

## Conflict Detection

`scripts/goal_conflict_detector.py` detects cross-goal conflicts from goal resource usage and the semantic resource map.

Conflict types:

- `resource`
- `schema`
- `api`
- `dependency`

Critical or high conflicts pause the lower-priority goal when conflict resolution is applied. The runtime never silently overwrites shared resources.

## Global Loop

`scripts/global_loop_engine.py` manages the goal set lifecycle.

It records:

- active goal
- paused goals
- backlog goals
- completed goals
- backend health
- system pressure
- global iteration
- actual execution freeze state

If backend health is unhealthy, actual execution is frozen and no Codex worker should run.

## Codex Isolation

Codex CLI remains only the execution backend for ready leaf tasks.

Codex does not:

- plan goals
- decompose big tasks
- aggregate parent results
- decide merges
- arbitrate conflicts

The scheduler and conflict detector run before execution. This preserves worktree and resource isolation.

## Single-goal Fallback

The runtime remains compatible with 0.6.x single-goal flows:

- `agent goal set`
- `agent plan-big`
- `agent decompose`
- `agent aggregate`
- `agent goal-loop`

0.7.0 adds global scheduling on top. If only one goal exists, the scheduler behaves like single-goal mode.

## CLI

```powershell
agent goal set "update docs" --priority 60 --resource README.md
agent goal list
agent goal schedule
agent goal conflicts --apply
agent global-loop
```

Goal lifecycle commands:

```powershell
agent goal pause --goal-id <goal-id>
agent goal resume --goal-id <goal-id>
agent goal backlog --goal-id <goal-id>
agent goal block --goal-id <goal-id>
agent goal complete --goal-id <goal-id>
```

## Safety Policy

- No real business project is modified by scheduler dry-runs.
- No merge or push is performed.
- No worktree is deleted.
- No secrets or `.env` contents are read.
- Multiple goals do not full-execute concurrently by default.
- The conflict detector cannot be bypassed by the scheduler.
- Global loop iterations are bounded.
