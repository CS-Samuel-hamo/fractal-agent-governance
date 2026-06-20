# Quickstart

For the product-facing quickstart, see [../QUICKSTART.md](../QUICKSTART.md).

Minimal flow:

```powershell
agent bootstrap --workspace .
agent backend switch mock
agent goal "make README onboarding clear"
agent run "add a short README note" --dry-run
agent status --no-write
```

Daily model:

```text
goal -> run -> result
```
