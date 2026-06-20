# Release Notes: v0.9.1-alpha

## UX Simplification

This release changes the public product surface from a system-oriented command set to a natural-language workflow:

```text
ask -> preview -> apply
```

## New Default Usage

```powershell
agent "fix README typo"
agent "fix README typo" -f README.md --apply
agent status
agent undo
```

Preview is the default. Applying changes requires `--apply`.

## What Changed From v0.9.0-alpha

- The homepage now teaches natural-language tasks first.
- Default output uses `task`, `mode`, and `result`.
- `-f <file>` is the short form for constraining a task to one file.
- System concepts are hidden from normal CLI help.
- Advanced diagnostics are available only through explicit debug commands.
- The runtime architecture remains unchanged; this is a product surface hardening release.
