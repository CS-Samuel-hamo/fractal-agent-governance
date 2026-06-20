# Governed Path Demo

```powershell
agent "change public API response and database schema" --workspace <repo> --dry-run
```

Expected:

- `route = governed`
- high-risk signals are recorded
- fast Codex path is not used
- review is required before merge readiness
