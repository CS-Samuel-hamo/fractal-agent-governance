# Checkpoint Runtime Policy

Zoo Code checkpoints are rollback evidence. They do not replace Git branches or commits.

Rules:

1. Each run-ledger transition may record `checkpoint_ref`.
2. Executor should record a pre-execution checkpoint before code edits when available.
3. Large, multi-file, or high-risk change must prompt for checkpoint confirmation.
4. Fallback, abort, and rollback reports must cite `checkpoint_ref` when available.
5. If Zoo Code does not expose checkpoint id, record:
   - task message timestamp
   - state
   - git diff stat
   - changed files
   - note: checkpoint available in Zoo Code UI

Checkpoint artifacts must include run_id, goal_id, branch_id, created_by_mode, model, created_at, input_artifacts, output_artifacts, and gate_status.
