# Quickstart

## 1. Preview a Task

```powershell
agent "add a short README note"
```

This is safe by default. The command previews the work and prints a concise result:

```json
{
  "task": "add a short README note",
  "mode": "preview",
  "result": "PREVIEW_READY"
}
```

## 2. Apply Only When Ready

```powershell
agent "add a short README note" -f README.md --apply
```

Use `--apply` only after the preview looks right.

## 3. Check Status

```powershell
agent status
```

## 4. Preview Undo

```powershell
agent undo
```
