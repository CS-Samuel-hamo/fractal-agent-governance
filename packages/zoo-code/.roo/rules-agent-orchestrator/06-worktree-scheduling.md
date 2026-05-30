# Worktree Scheduling

The orchestrator may schedule parallel exploration only after GPT branch-manager approval.

Required artifacts:

- branch contracts
- branch-schedule.json
- worktree-map.json
- path-locks.json
- merge-queue.json

Parallel group rules:

- no high/critical risk
- no security/auth/payment/PII/migration
- owned_paths do not overlap
- shared_paths declared
- provides/consumes stable
- independent acceptance and verification
- Git worktree isolation

After children complete, orchestrator sends branch evidence to parent aggregation. No child branch may merge directly.
