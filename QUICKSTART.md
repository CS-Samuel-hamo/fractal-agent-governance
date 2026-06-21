# Quickstart

This guide shows the 5-minute path for the public alpha.

## 1. Open Or Refresh The Cockpit

```bash
agent cockpit
```

Open the printed local file path in your browser. The Cockpit is a static local page. It does not require a server or network.

## 2. Start A Project Session

```bash
agent start "prepare this project for public release"
```

The session reads the project map, selects the next useful action, and records progress locally.

## 3. Check Progress

```bash
agent status
```

Status shows the current session state, next action, digest path, and Cockpit path.

## 4. Continue, Stop, Or Undo

```bash
agent continue
agent stop
agent undo
```

Use `continue` to advance the session, `stop` to pause safely, and `undo` to inspect the latest recovery point.

## 5. Generate Release And PR Artifacts

```bash
agent release
agent pr
```

These commands generate local artifacts only:

- release readiness report
- release notes draft
- changelog draft
- release action plan
- PR plan
- PR draft

They do not call GitHub, push, merge, create a remote PR, read tokens, or read `.env` contents.

## If A Worker Is Unavailable

The product can still run in preview, dry-run, or local scan mode. An unavailable worker is reported as a capability limitation, not a fatal product failure.

## One-off Task Preview

```bash
agent "fix README typo"
```

Task commands preview by default. Use `--apply` only when you explicitly want changes.
