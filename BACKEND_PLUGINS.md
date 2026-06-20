# Advanced Execution Providers

This file is for maintainers and advanced local setups.

Most users do not need this page. The normal product path is:

```powershell
agent "fix README typo"
agent "fix README typo" --apply
```

## Advanced Configuration

Agent Runtime can use replaceable execution providers for tests, dry runs, and local execution.

```powershell
agent config backend mock
agent debug backend list
```

Provider failures must return structured failure results. They must not produce false success or mutate user state outside the requested task.
