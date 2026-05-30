# Checkpoint Runtime

Record Zoo Code checkpoint references as rollback evidence when available.

- before executor edits, record pre-execution checkpoint when available
- large, multi-file, high-risk, or Level 3/4 work must confirm checkpoint availability or record why unavailable
- fallback, abort, and rollback reports must cite checkpoint_ref when available
- checkpoint_ref may be task timestamp plus state and git diff stat when Zoo Code does not expose an id
- checkpoint is not Git history; final integration still uses branch/commit evidence
