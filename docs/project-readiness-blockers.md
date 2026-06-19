# Project Readiness Blockers

Project readiness classifies local state before daily alpha use.

Blocker types:

- `dirty_worktree`
- `unborn_repo`
- `nested_git_repo`
- `initial_commit_timeout`
- `stale_git_index_lock`
- `missing_git_repo`
- `codex_unavailable`
- `codex_home_unavailable`
- `test_command_unknown`
- `large_untracked_set`
- `bootstrap_file_conflict`
- `unsafe_existing_state`

`project-readiness.json` includes:

```json
{
  "safe_for_bootstrap": true,
  "safe_for_level_0_1_trial": true,
  "safe_for_codex_actual_run": true,
  "blockers": []
}
```

Rules:

- Dirty worktrees block actual real-project runs.
- Unborn repos block actual runs until the user creates an explicit initial commit.
- Nested git repos block bootstrap commits and actual runs until the user decides submodule/ignore/remove.
- Large untracked sets are warnings or blockers by size.
- Bootstrap never performs `git add all` or an automatic initial commit.
