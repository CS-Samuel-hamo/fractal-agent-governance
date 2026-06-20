# CLI Reference

## Version

```powershell
agent --version
```

## Ask

```powershell
agent "<task>"
agent "<task>" --preview
agent "<task>" -f <file> --apply
```

Default mode is preview. Use `--apply` to allow changes.

Use `-f` when you want to limit the task to one file:

```powershell
agent "fix README typo" -f README.md --apply
```

## Status

```powershell
agent status
```

Shows the current task summary.

## Undo

```powershell
agent undo
```

Previews the latest undo plan.

## Help

```powershell
agent --help
agent status --help
agent undo --help
```
