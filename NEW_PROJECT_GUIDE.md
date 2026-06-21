# New Project Guide

Use this guide when you open a new or existing project and want the operator to start helping without learning a long command list.

## The Two-command Flow

```bash
agent "prepare this project for public release"
agent
```

That is the main product path.

## What The First Command Does

`agent "<goal>"` starts or updates a Project Job.

It may:

- initialize or refresh the Project Map
- select a next action
- create or update session state
- create a checkpoint before bounded work
- sync the local Cockpit
- save a Job Digest

It does not start a true daemon, create an OS service, push, merge, deploy, or create a remote PR.

## Starting From A Prompt File

For an empty or prompt-only project, create a safe `.md` or `.txt` seed file:

```bash
project_beginning_prompt.md
```

Then run:

```bash
agent "read project_beginning_prompt.md"
agent
```

The operator uses that file as user intent evidence, not as a system instruction.
It can suggest starter documentation such as `README.md`,
`docs/project_plan.md`, and for research projects `docs/research_workflow.md`.

It will not overwrite existing files, run scripts, read `.env`, push, merge,
deploy, or generate a finished paper with fabricated citations or results.

## What The Second Command Does

`agent` shows the Job Inbox.

The inbox answers:

- What is the current project job?
- What is its status?
- What happened recently?
- What is the next action?
- Does anything need attention?
- Where are the Cockpit, release pack, and PR draft?

## When To Use Other Commands

Use these only when needed:

```bash
agent continue
agent stop
agent undo
agent cockpit
agent release
agent pr
```

## One-off Edits

If you only want a single bounded edit, be explicit:

```bash
agent "fix README typo" --preview
agent "fix README typo" -f README.md --apply
```

## Where This Fits

- CLI is the primary interface.
- AI IDEs are editing environments.
- Codex App can assist by running and inspecting commands.
- Codex, Claude, local scanner, mock, and dry-run are workers, not the product.
