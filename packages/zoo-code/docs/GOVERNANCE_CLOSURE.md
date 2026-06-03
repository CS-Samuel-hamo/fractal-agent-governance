# Governance Closure Layer

This layer turns reviewer rules into executable, auditable run artifacts.

## Artifacts

For each run, the closure layer writes or reads:

- `.zoo-agent/runs/<run-id>/risk-register.json`
- `.zoo-agent/runs/<run-id>/task-board-consistency.json`
- `.zoo-agent/runs/<run-id>/quality-gate.json`
- `.zoo-agent/runs/<run-id>/merge-queue.json`
- `.zoo-agent/runs/<run-id>/merge-queue-processing.json`
- `.zoo-agent/locks/resource-locks.json`

## Commands

Check task-board consistency:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\check_task_board_consistency.py `
  --workspace "<repo>" `
  --run-id "<run-id>"
```

Add or close run risks:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\update_risk_register.py `
  --workspace "<repo>" `
  --run-id "<run-id>" `
  --add `
  --title "Provider profile access remains unverified" `
  --severity high `
  --source reviewer

python $env:USERPROFILE\.roo\agent-governance-kit\scripts\update_risk_register.py `
  --workspace "<repo>" `
  --run-id "<run-id>" `
  --close `
  --risk-id risk-001 `
  --resolution "Carried into integration checklist"
```

Run the quality gate:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\run_quality_gate.py `
  --workspace "<repo>" `
  --run-id "<run-id>"
```

Authorize queue processing only after the evidence is clean:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\run_quality_gate.py `
  --workspace "<repo>" `
  --run-id "<run-id>" `
  --authorize-merge-queue
```

Process the queue into a serial integrator contract:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\process_merge_queue.py `
  --workspace "<repo>" `
  --run-id "<run-id>" `
  --authorize `
  --authorization-note "Quality gate passed and parent aggregation reviewed"
```

## Safety Boundary

`process_merge_queue.py` does not run `git merge`, deploy, release, provider
probes, data updates, cache mutation, or durable-state writes. It only records
that the queue is ready for a serial integrator and writes the contract the
integrator must follow.

## Resource Locks

Parallel workers acquire active locks through:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\manage_resource_locks.py `
  --workspace "<repo>" `
  --run-id "<run-id>" `
  --owner "<worker-owner>" `
  --conflict-key "src/service" `
  --acquire
```

`run_codex_parallel_workers.py` uses these locks by default before launching a
leaf worker and releases them when the leaf finishes. Use
`--skip-global-locks` only for diagnostics.
