# Existing Project Onboarding

Run:

```powershell
agent bootstrap --workspace <existing-git-repo>
```

Bootstrap performs metadata-only scanning and writes reviewable runtime files:

- `.zoo-agent/project-profile.json`
- `.zoo-agent/project-readiness.json`
- `.zoo-agent/bootstrap-report.md`
- `.zoo-agent/bootstrap.lock`
- `AGENTS.md` when missing
- `AGENTS.md.new` when an active `AGENTS.md` already exists and refresh is requested
- `.gitignore.agent.patch` when `.gitignore` exists
- `.roo/rules.new/...` when `.roo/rules` already exists

It does not edit `src`, `tests`, `backend`, `frontend`, or other business source directories. It does not commit.

Existing project safety rules:

- Bootstrap never runs `git add .` or any `git add all` equivalent.
- Bootstrap never creates an initial commit.
- Bootstrap writes only governance files, proposals, and patches.
- `project-readiness.json` reports blockers such as `dirty_worktree`, `nested_git_repo`, and `stale_git_index_lock`.
- Suggested files to commit must be reviewed by the user before any manual commit.

Second bootstrap:

```powershell
agent bootstrap --workspace <existing-git-repo>
```

If `bootstrap.lock` exists and required artifacts are present, bootstrap exits as already bootstrapped and does not overwrite project files.
