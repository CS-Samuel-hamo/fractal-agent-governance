# Checkpoint Runtime

Record Zoo Code checkpoint references as rollback evidence when available.

- before executor edits, record pre-execution checkpoint when available
- large, multi-file, high-risk, or Level 3/4 work must confirm checkpoint availability or record why unavailable
- fallback, abort, and rollback reports must cite checkpoint_ref when available
- checkpoint_ref may be task timestamp plus state and git diff stat when Zoo Code does not expose an id
- checkpoint is not Git history; final integration still uses branch/commit evidence
- Git branch/worktree commits are formal rollback anchors and merge queue evidence.
- stash/patch output is temporary evidence for abandoned or redo-needed work, not final integration fact.
- rollback-branch-worktree.py must default to a rollback plan; it must not delete worktrees or run destructive reset commands by default.
