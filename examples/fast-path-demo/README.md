# Fast Path Demo

```powershell
agent "fix typo in README" --workspace <repo> --dry-run
```

Expected:

- `route = fast`
- no full planning
- no fractal decomposition
- no product docs
- minimal report with timing metrics
