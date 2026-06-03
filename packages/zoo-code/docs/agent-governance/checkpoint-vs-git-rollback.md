# Checkpoint Vs Git Rollback

Zoo checkpoint and Git rollback are related but not equivalent.

Zoo checkpoint:

- Interactive recovery.
- Quick comparison.
- Safety cushion around AI edits.
- Not formal Git history.
- Not the only rollback anchor.

Git branch/worktree commit:

- Auditable history.
- Merge queue input.
- Rollback anchor.
- Integration decision evidence.

Patch/stash:

- Temporary preservation.
- Evidence for abandoned or redo-needed branches.
- Not final integration fact source.

`rollback-branch-worktree.py` should default to producing a rollback plan, not deleting worktrees or running destructive reset commands.
