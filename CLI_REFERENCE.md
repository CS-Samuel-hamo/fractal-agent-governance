# CLI Reference

The normal user model is:

```text
project goal -> job -> inbox -> progress
```

## Daily Path

### `agent "<goal>"`

Start or update the current Project Job.

```bash
agent "prepare this project for public release"
```

Without `--preview` or `--apply`, a natural-language command is treated as a project job. The job reuses the existing session runtime, project map, worker router, checkpoints, and Cockpit sync.

For prompt-only projects, this also supports safe seed prompt bootstrap:

```bash
agent "read project_beginning_prompt.md"
```

Safe root-level or `docs/` `.md` / `.txt` seed files are used as intent
evidence. The operator may create or preview starter documentation, but it will
not run scripts, read secrets, overwrite existing files, push, merge, deploy, or
fabricate research claims.

### `agent`

Show the Job Inbox.

```bash
agent
```

The inbox shows current job, status, what happened, next action, attention items, available outputs, and suggested commands.

### `agent status`

Explicit alias for `agent`.

```bash
agent status
```

Use this when you prefer a named command, but day to day `agent` is enough.

## Steering Commands

### `agent continue`

Continue the current job/session by one bounded step.

```bash
agent continue
```

### `agent stop`

Safely stop the current job without deleting artifacts.

```bash
agent stop
```

### `agent undo`

Inspect the latest recovery point and keep job state in sync.

```bash
agent undo
```

### `agent cockpit`

Generate or refresh the local Project Cockpit.

```bash
agent cockpit
```

## Release Preparation

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

## One-off Task Mode

Use explicit flags when you want a bounded single task instead of a Project Job.

```bash
agent "fix README typo" --preview
agent "fix README typo" --apply
agent "fix README typo" -f README.md --apply
```

If `--apply` reports that actual execution is unavailable, run:

```bash
agent workers --doctor
```

The doctor explains which worker roles are available locally and whether actual
code execution is currently supported.

## Compatibility Commands

These still work, but they are not the main user path:

```bash
agent start "<project goal>"
agent status
```

`agent start "<goal>"` is an explicit alias for `agent "<goal>"`.

## Developer Diagnostics

The alpha includes hidden diagnostics for maintainers. They do not appear in normal help and are not part of the public user path.

Examples include worker, learning, release safety, feedback, and launch audit commands.
