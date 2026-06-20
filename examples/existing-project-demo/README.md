# Existing Project Demo

Use a temporary git project:

```powershell
agent bootstrap --workspace <temp-existing-git-repo>
agent status --workspace <temp-existing-git-repo> --no-write
agent "fix typo in README" --workspace <temp-existing-git-repo> --dry-run
```

Expected:

- bootstrap writes `.zoo-agent/project-profile.json`
- bootstrap writes `.zoo-agent/project-readiness.json`
- bootstrap writes `.zoo-agent/bootstrap-report.md`
- bootstrap writes `.zoo-agent/bootstrap.lock`
- business source directories are unchanged
