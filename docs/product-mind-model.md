# Product Mind Model

Agent Runtime should feel like a small assistant you can ask to work safely.

```text
ask -> preview -> apply
```

## Ask

Say what you want:

```powershell
agent "fix README typo"
```

## Preview

Preview is the default. The tool reports what it can do without applying changes.

```json
{
  "task": "fix README typo",
  "mode": "preview",
  "result": "PREVIEW_READY"
}
```

## Apply

Apply is explicit:

```powershell
agent "fix README typo" -f README.md --apply
```

## Result

The normal output uses three fields:

- `task`: what you asked for
- `mode`: preview, apply, status, or blocked
- `result`: the concise outcome

Normal users do not need to learn internal implementation terms. Debug details are available only through explicit debug commands.
