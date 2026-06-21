# Quickstart

This guide shows the simplest path for the public alpha.

## Most Usage Is Two Commands

```bash
agent "prepare this project for public release"
agent
```

The first command starts or updates a Project Job. The second command shows the Job Inbox: current status, what happened, what needs attention, and what to do next.

## 1. Start A Project Job

```bash
agent "prepare this project for public release"
```

This creates a durable job backed by the existing session runtime. It does not start a true daemon or OS service. It makes one safe bounded step, saves state, and lets you come back later.

If the project starts from a single prompt file, use the same command style:

```bash
agent "read project_beginning_prompt.md"
```

Safe root-level or `docs/` `.md` / `.txt` files are treated as seed intent
evidence. The operator should produce a clear next state: a starter docs action,
a preview, or a specific blocked reason. It should not show a vague `blocked
zone` with no explanation.

## 2. Check Later

```bash
agent
```

This shows the current job, status, next action, attention items, Cockpit path, and suggested commands.

`agent status` still works, but it is now just the explicit form of `agent`.

## 3. Open The Cockpit

```bash
agent cockpit
```

The Cockpit is a static local page. It does not require a server or network.

## 4. Steer When Needed

```bash
agent continue
agent stop
agent undo
```

Use these only when you want to steer the current job.

## 5. Prepare Release And PR Artifacts

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

## One-off Task Mode

For a bounded single task, be explicit:

```bash
agent "fix README typo" --preview
agent "fix README typo" --apply
```

Use `-f README.md` when you want to keep a one-off edit scoped to a file.

## Where To Use It

- CLI is the primary interface.
- AI IDEs are good editing environments.
- Codex App can assist by running, inspecting, and explaining agent commands.
- Codex, Claude, local scanner, mock, and dry-run are workers, not the product.
