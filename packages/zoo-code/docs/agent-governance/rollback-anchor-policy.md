# Rollback Anchor Policy

Rollback plans should record:

- `checkpoint_ref` when available.
- Git branch.
- Worktree path.
- Last commit.
- Diff stat.
- Patch path if created.
- Rollback anchor type: checkpoint, git commit, patch, or manual.

High-risk rollback requires GPT or human confirmation. Worktrees are not deleted automatically.
