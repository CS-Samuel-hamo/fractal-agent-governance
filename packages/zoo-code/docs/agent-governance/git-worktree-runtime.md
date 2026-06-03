# Git Worktree Runtime

Worktrees are used for isolated branch execution and parallel exploration. They are required for every branch scheduled into a parallel group and optional for serial branches.

## Artifacts

- `.zoo-agent/runs/<run-id>/worktree-map.json`
- `.zoo-agent/runs/<run-id>/branch-schedule.json`
- `.zoo-agent/runs/<run-id>/path-locks.json`
- `.zoo-agent/runs/<run-id>/merge-queue.json`

## Rules

1. Fractal branch does not imply concurrency.
2. Default execution is dependency-ordered and sequential.
3. Parallel coding requires Git worktree isolation.
4. Parallel branch completion enters merge queue, never direct merge.
5. Integration branch is single-threaded.
6. GPT branch-manager/orchestrator decides parallel group.
7. GPT integrator serially processes merge queue.
8. DeepSeek cannot decide parallel safety or final merge.
9. Every scheduled worktree branch records a checkpoint ref before executor edits.
10. The scheduler records branch state in run-ledger and artifact-graph before execution.
11. Completed branches must pass reconciliation before parent aggregation.
12. Failed branches must be blocked from merge queue and receive a rollback or redecomposition plan.

## Worktree Map Schema

```json
{
  "run_id": "",
  "branches": [
    {
      "branch_id": "",
      "git_branch": "",
      "worktree_path": "",
      "base_branch": "",
      "status": "planned|created|active|review|queued|merged|abandoned|archived",
      "owned_paths": [],
      "shared_paths": [],
      "checkpoint_refs": [],
      "merge_queue_item": "",
      "phase_id": "",
      "requires_checkpoint_before_execution": true
    }
  ]
}
```

Rollback tooling is governance-first and non-destructive by default. `scripts/rollback-branch-worktree.py` records checkpoint refs and blocks merge queue entries; it does not delete worktrees or run destructive git commands.
