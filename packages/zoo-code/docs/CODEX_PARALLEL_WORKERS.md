# Codex Parallel Workers

Codex CLI can be used as a parallel worker process, but Zoo owns the scheduler.
Do not run multiple `codex exec` processes in the same workspace.

## Parallel Contract

Parallel Codex execution is allowed only for leaf tasks that pass all of these
checks:

- each leaf is `parallelizable: true`;
- each leaf recommends `optimistic_worker` unless an operator explicitly allows
  planned workers;
- no hard-risk objective or file surface is detected;
- every leaf has non-empty, non-overlapping `conflict_keys`;
- no leaf owns `repo:*`;
- every leaf has a unique task id, worktree root, worker log directory, task
  pack path, final-message path, and result path.

The parent workstream is never executed in parallel. Parent aggregation and
merge queue processing remain serial and gated.

## Commands

Check a generated Level 3 leaf index:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\check_codex_worker_concurrency.py `
  --workspace "<repo>" `
  --run-id "<run-id>" `
  --leaf-index ".zoo-agent\runs\<run-id>\fractal-workstreams\<task-id>\leaf-tasks\leaf-tasks.json"
```

Run safe leaf workers concurrently:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\run_codex_parallel_workers.py `
  --workspace "<repo>" `
  --run-id "<run-id>" `
  --leaf-index ".zoo-agent\runs\<run-id>\fractal-workstreams\<task-id>\leaf-tasks\leaf-tasks.json" `
  --max-workers 2 `
  --codex-home D:\AI_DEV\codex_home
```

Use `--dry-run` to write only the schedule and resource locks. Use
`--worker-dry-run` to launch each leaf dispatcher in dry-run mode without
starting Codex.

## Artifacts

The scheduler writes:

- `.zoo-agent/runs/<run-id>/parallel-workers/<parent-task>/concurrency-check.json`
- `.zoo-agent/runs/<run-id>/parallel-workers/<parent-task>/resource-locks.json`
- `.zoo-agent/runs/<run-id>/parallel-workers/<parent-task>/branch-schedule.json`
- `.zoo-agent/runs/<run-id>/parallel-workers/<parent-task>/parallel-run.json`
- `.zoo-agent/runs/<run-id>/parallel-workers/<parent-task>/<leaf-task>/worker-result.json`
- `.zoo-agent/locks/resource-locks.json`
- `.zoo-agent/runs/<run-id>/merge-queue.json`
- `.zoo-agent/runs/<run-id>/parent-aggregation.json`

The merge queue written by the scheduler is record-only:

```text
record_only_parallel_candidates_not_processable
```

It does not authorize merge, release, deploy, provider probes, data updates,
cache mutation, or durable-state changes.

## CODEX_HOME

The default is shared `CODEX_HOME`. If session/cache contention appears, use:

```powershell
--worker-codex-home-root "D:\AI_DEV\codex_home_workers"
```

That gives each leaf a separate `CODEX_HOME`, but may require separate auth or
configuration.

## Active Resource Locks

`check_codex_worker_concurrency.py` checks conflicts inside one leaf index.
`run_codex_parallel_workers.py` also acquires active locks in
`.zoo-agent/locks/resource-locks.json` before each leaf starts and releases them
when the leaf exits. If another run owns the same conflict key, the leaf is
recorded as `blocked_by_global_resource_lock` instead of being launched.

Use `--skip-global-locks` only for diagnostics or smoke tests where no real
workspace mutation is possible.
