# CLI Reference

The normal user model is:

```text
project goal -> safe batch -> project overview -> next choice
```

Agent Runtime is an AI Project Operator. Its main visible product surface is the beginner-friendly interaction summary, not backend configuration. The summary is backed by the Project Map and explains the result, current position, changed files, verification path, recommended next action, recovery options, and details.

## Daily Path

### `agent "<goal>"`

Start or update the current Project Job and execute one safe, reviewable batch when possible.

```bash
agent "prepare this project for public release"
```

Without `--preview` or `--apply`, a natural-language command is treated as the main operator input. The job reuses the existing session runtime, project map, checkpoints, and Cockpit sync, but normal output stays focused on project progress instead of implementation details.

For prompt-only projects, this also supports safe seed prompt bootstrap:

```bash
agent "read project_beginning_prompt.md"
```

Safe root-level or `docs/` `.md` / `.txt` seed files are used as intent
evidence. The operator may create or preview starter documentation, but it will
not run scripts, read secrets, overwrite existing files, push, merge, deploy, or
fabricate research claims.

### `agent do "<task>"`

Run an independent one-off task without replacing the current project job.

```bash
agent do "show me how the current workflow is wired"
agent do "extend docs/research_workflow.md with evidence validation steps"
```

Use this when you want a temporary explanation, review, example, or bounded file edit that sits outside the main project goal. If the task names a safe documentation target, Agent may update that file. If the task looks like a broader project goal, Agent writes a temporary preview artifact under `.zoo-agent/previews/` and leaves the current job unchanged.

### `agent`

Show the Project Overview / Job Inbox.

```bash
agent
```

The status view shows:

```text
Result
Where you are
What changed
How to check
Next
If this is not what you wanted
Details
```

`Details` contains the Project Map view, Landing proof, Project Rules, Logic Check, and job metadata.

### `agent status`

Explicit alias for `agent`.

```bash
agent status
```

Use this when you prefer a named command, but day to day `agent` is enough.

## Steering Commands

### `agent continue`

Continue the current job/session by one bounded step only when `Next` explicitly recommends it.

```bash
agent continue
```

If the current batch is complete, `agent` will say continue is not needed. Prefer giving the next goal directly:

```bash
agent "continue improving the docs toolkit"
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

## Advanced Preview / Apply Flags

Use explicit flags only when you need compatibility with the old preview/apply flow.

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
