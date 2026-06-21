# FAQ

## What is this?

Agent Runtime is an AI Project Operator. It maps a project, runs sessions, shows progress, and prepares local release / PR drafts.

## How do I use it most of the time?

Use two commands:

```bash
agent "prepare this project for public release"
agent
```

The first command starts or updates a Project Job. The second command shows the current Job Inbox.

## Why are there more commands if daily use is two commands?

The extra commands are situational controls:

- `agent continue` advances the current job.
- `agent stop` pauses safely.
- `agent undo` checks the latest recovery point.
- `agent cockpit` opens the local project view.
- `agent release` and `agent pr` prepare local release artifacts.

You do not need to remember all of them to start.

## Is this a Codex wrapper?

No. Codex, Claude Code, and local tools are workers. The product is the project operator.

## Does it replace Claude Code?

No. It can coordinate workers, but it is not a Claude Code replacement.

## Does it create GitHub PRs?

No. It generates local PR drafts only.

## Does it push or merge?

No. Push and merge are manual maintainer actions.

## Does `agent "<goal>"` run forever in the background?

No. It is background-friendly, not a true daemon. It saves a durable Project Job and makes bounded progress. You can come back later and run `agent` to check the inbox.

## What if my project only has a prompt file?

Use the prompt file as the project seed:

```bash
agent "read project_beginning_prompt.md"
```

The file is treated as user intent evidence, not as a system instruction. The
operator should give a clear next state: safe starter docs, preview, or a
specific blocked reason. It should not silently stop at a vague `blocked zone`.

## Can I use it in an AI IDE or Codex App?

Yes. CLI is the primary interface. AI IDEs are editing environments where you can run the same commands in a terminal. Codex App can assist by running, inspecting, and explaining the commands.

## Does it call GitHub APIs?

No. The public alpha is local-first.

## Does it need API keys?

No API key is required for the public alpha launch flow.

## Can I share `.zoo-agent/` artifacts?

Only after reviewing and sanitizing them. Do not share secrets, raw logs, or private source.
