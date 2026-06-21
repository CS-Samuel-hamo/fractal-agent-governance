# CLI Reference

The normal user model is:

```text
ask -> preview -> apply
project goal -> session -> progress -> release pack
```

## Public Commands

### `agent "<task>"`

Preview a one-off task.

```bash
agent "fix README typo"
```

### `agent "<task>" --preview`

Explicit preview mode. This is equivalent to the default one-off task mode.

```bash
agent "add a quickstart note" --preview
```

### `agent "<task>" --apply`

Apply a bounded one-off task.

```bash
agent "fix README typo" -f README.md --apply
```

Use `-f` to keep the task scoped to a specific file.

### `agent start "<project goal>"`

Start a durable project session.

```bash
agent start "prepare this project for public release"
```

### `agent status`

Show the current project session state and useful next command.

```bash
agent status
```

### `agent continue`

Continue the current session.

```bash
agent continue
```

### `agent stop`

Safely stop the current session without deleting artifacts.

```bash
agent stop
```

### `agent undo`

Inspect the latest recovery point.

```bash
agent undo
```

### `agent cockpit`

Generate or refresh the local Project Cockpit.

```bash
agent cockpit
```

### `agent release`

Generate a local release workflow pack.

```bash
agent release
```

This does not push, merge, deploy, or call GitHub.

### `agent pr`

Generate a local PR plan and PR draft.

```bash
agent pr
```

This does not create a remote PR.

## Developer Diagnostics

The alpha also includes hidden diagnostics for maintainers. They do not appear in normal help and are not part of the public user path.

```bash
agent workers --doctor
agent learning --build
agent release --safety-check
agent alpha --audit
```

Use these for local validation, not for normal project operation.
