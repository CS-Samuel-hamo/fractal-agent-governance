# Parallel Branch Execution Policy

Default integration inside one orchestrator run is dependency ordered and sequential. Branch scheduling is proactive: once a root goal produces child branch contracts, GPT branch-manager/orchestrator evaluates whether safe branches can run in parallel. If parallel is unsafe, the scheduler records serial execution or `needs_decomposition` instead of leaving the decision implicit.

## Parallel Eligibility

Branches may run concurrently only when all conditions are true:
- `owned_paths` do not overlap
- `shared_paths` are declared
- `provides` and `consumes` contracts are stable
- no branch has high or critical risk
- no branch touches security, auth, payment, PII, or migration work
- each branch has independent acceptance criteria
- each branch has independent verification plan
- each branch uses Git worktree isolation
- path locks have no conflict
- GPT branch-manager/orchestrator approves the parallel group
- each branch has a rollback checkpoint before executor edits

Coding in parallel must use Git worktrees. Completed parallel branches enter merge queue and never merge directly. Parent aggregation must pass before integrator. DeepSeek cannot decide parallel safety; GPT branch-manager or orchestrator decides the parallel group.

## Active Scheduling

Use `scripts/schedule-parallel-branches.py` after branch contracts exist. It generates:

- `.zoo-agent/runs/<run-id>/branch-schedule.json`
- `.zoo-agent/runs/<run-id>/worktree-map.json`
- `.zoo-agent/runs/<run-id>/path-locks.json`
- `.zoo-agent/runs/<run-id>/merge-queue.json`
- `.zoo-agent/runs/<run-id>/parent-aggregation-matrices.json`
- `.zoo-agent/runs/<run-id>/parallel-metrics.json`
- `.zoo-agent/runs/<run-id>/parallel-execution-report.md`

It also updates run-ledger branch state and artifact-graph dependency/merge order. The scheduler does not merge branches and does not allow direct parallel integration.

## Post-Execution Reconciliation

Parallel safety is a hypothesis until the branch has produced actual changes. After each child branch completes, run:

```bash
python scripts/reconcile-branch-completion.py --run-id <run-id> --branch-id <branch-id> --diff-name-only
```

The reconciliation gate checks actual changed file names against path locks, shared-path approval, completion evidence, obligation ledger, diagnostics report, quality gate, and review report. Failure blocks the merge queue entry and marks the branch for rollback or redecomposition.

Before final parent integration, run:

```bash
python scripts/parent-aggregation-gate.py --run-id <run-id>
```

If aggregation fails, record rollback/redecomposition:

```bash
python scripts/rollback-branch-worktree.py --run-id <run-id> --branch-id <branch-id> --reason "<reason>"
```

Rollback planning is non-destructive by default. It records checkpoint refs, worktree path, blocked merge queue state, and the parent-level next action.
