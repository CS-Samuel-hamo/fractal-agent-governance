# Multi-goal Execution Governance Lock

Agent Runtime 0.7.4 locks two production-safety rules:

1. System/runtime/diagnostic goals do not compete with user production goals.
2. Codex backend health is an execution gate, not an advisory signal.

## Goal Domains

Goals are classified as:

- `production_goal`: user work; eligible for production scheduler.
- `system_goal`: bootstrap, scheduler self-check, loop repair, runtime maintenance; excluded from production scheduler.
- `runtime_goal`: metrics and backend health maintenance; background only.
- `diagnostic_goal`: debug, validation, smoke, or dry-run goals; dry-run only.

The default scheduler queue is production-only. Excluded goals are reported in `goal-schedule.json` as `excluded_goals` with `exclusion_reason`.

## Backend Health Gate

Codex health verdicts control actual execution:

- `HEALTHY`: actual execution is allowed; parallel actual may run only after independence checks.
- `HEALTHY_WITH_WARNINGS`: only one low-risk fast/leaf actual is allowed; parallel actual is blocked.
- `UNHEALTHY`: all Codex actual execution is blocked; dry-run, planning, decomposition, and reporting remain allowed.

Diagnostic goals never trigger Codex actual execution, even when the backend is healthy.

## Governance Invariants

- System goals do not affect production priority queues.
- System goals do not affect production starvation calculations.
- System goals do not determine production convergence.
- Backend health failures cannot be bypassed by scheduler priority.
- `--skip-health-check` skips running a new check, but it does not bypass the cached health execution gate.

