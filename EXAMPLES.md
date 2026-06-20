# Examples

## Documentation Dry-run

```powershell
agent backend switch mock
agent run "add a README troubleshooting note" --dry-run --allowed-file README.md
```

## Small Code Task

```powershell
agent goal "improve local utility reliability"
agent run "add one unit test for the local utility module" --dry-run --allowed-file <TEST_FILE>
```

## Backend Selection

```powershell
agent backend list
agent backend health
agent backend switch dry_run
```

## Status

```powershell
agent status --no-write
```

## Safe Rollback Planning

```powershell
agent rollback --run-id <run-id> --task-id <task-id> --dry-run
```

Rollback defaults to a plan. It does not run `git reset --hard`.
