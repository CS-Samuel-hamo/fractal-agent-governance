# Parallel Path Demo

```powershell
agent run --parallel --workspace <repo> --dry-run "update docs/a.md" "update docs/b.md"
```

Expected:

- route is parallel when independence is known
- otherwise `parallel_denial_reason` is written
- no merge occurs
