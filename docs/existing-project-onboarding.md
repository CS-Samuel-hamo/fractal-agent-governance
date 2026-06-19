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

Second bootstrap:

```powershell
agent bootstrap --workspace <existing-git-repo>
```

If `bootstrap.lock` exists and required artifacts are present, bootstrap exits as already bootstrapped and does not overwrite project files.
