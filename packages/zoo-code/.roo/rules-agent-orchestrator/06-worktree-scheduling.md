# Worktree Scheduling

The orchestrator schedules parallel exploration only after GPT branch-manager approval and writes the decision through `scripts/generate-branch-schedule.py` or `scripts/schedule-parallel-branches.py`.

Required artifacts:

- branch contracts
- branch-schedule.json
- worktree-map.json
- path-locks.json
- resource-locks.json
- merge-queue.json
- run-ledger branch states
- artifact-graph branch dependencies
- checkpoint refs
- parent aggregation matrices
- parallel metrics
- parallel denial reasons

Parallel group rules:

- no high/critical risk
- no security/auth/payment/PII/migration
- owned_paths do not overlap
- semantic resources do not conflict
- shared_paths declared
- provides/consumes stable
- independent acceptance and verification
- Git worktree isolation
- rollback checkpoint before executor edits
- root/parent aggregation nodes are not executable leaf branches
- merge queue after completion

After children complete, orchestrator sends branch evidence to parent aggregation. No child branch may merge directly.
