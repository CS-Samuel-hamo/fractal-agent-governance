# AI Project Operator

Give it a project. It keeps moving it forward.

Agent Runtime is a local-first AI Project Operator. It builds a project map, starts a durable work session, chooses the next project-level action, coordinates available AI workers, shows progress in a local Cockpit, and prepares release or PR-ready artifacts.

It is not a Codex wrapper, a Claude Code replacement, a generic AI coding CLI, or a GitHub bot. Codex, Claude Code, local scanner, mock, and dry-run modes are workers. The product is the project operator layer that keeps the project moving.

Version: `v1.0.0-alpha.1`

Current patch level: `1.0.5-intent-first-seed-bootstrap`

## Quick Demo

```bash
agent "prepare this project for public release"
agent
agent release
agent pr
```

The public path is:

1. Give the operator a project goal.
2. Come back and run `agent` to see the Job Inbox.
3. Continue, stop, undo, or open Cockpit when needed.
4. Generate a local release and PR pack.

Most usage is two commands:

```bash
agent "<goal>"
agent
```

You do not need to remember every command. Other commands are situational.

For a brand-new project that starts from a prompt or brief file, put the file in
the project root or `docs/`, then run:

```bash
agent "read project_beginning_prompt.md"
agent
```

The operator treats safe `.md` / `.txt` prompt files as seed intent evidence. It
may propose or preview starter docs such as `README.md`, `docs/project_plan.md`,
or `docs/research_workflow.md`; it will not treat the prompt as a system
instruction, read secrets, run scripts, push, merge, deploy, or fabricate
citations/results.

## What It Does

- Maintains a local Project Map with modules, capabilities, risks, and next actions.
- Runs long-lived project sessions that can continue after interruption.
- Uses worker roles for scanning, previewing, code work, tests, and dry runs.
- Keeps normal output focused on project progress, not implementation details.
- Generates local release readiness, PR draft, release notes, changelog draft, and action plan.
- Opens a static local Cockpit at `.zoo-agent/cockpit/index.html`.

## Safe Local Defaults

- No GitHub API calls.
- No network requirement for release or PR pack generation.
- No automatic push, merge, remote PR creation, or deployment.
- No `.env` content or API key reading.
- Runtime artifacts stay local under `.zoo-agent/`.

## Install

See [INSTALL.md](INSTALL.md).

## Start in 5 Minutes

See [QUICKSTART.md](QUICKSTART.md).

## Public Commands

Daily path:

```bash
agent "<goal>"
agent
```

Steer the current job:

```bash
agent continue
agent stop
agent undo
agent cockpit
```

Prepare release artifacts:

```bash
agent release
agent pr
```

One-off task mode is still available when you explicitly ask for it:

```bash
agent "fix README typo" --preview
agent "fix README typo" --apply
```

See [CLI_REFERENCE.md](CLI_REFERENCE.md) for details.

For new projects, see [NEW_PROJECT_GUIDE.md](NEW_PROJECT_GUIDE.md).

## Demo Project

See [DEMO.md](DEMO.md) and `examples/demo_project/`.

## Product Positioning

Project-level Autopilot, not task-level coding agent.

The main difference is that Agent Runtime works from a Project Map and durable session state. It does not just answer one coding prompt; it tracks what the project is, what has changed, what is blocked, and what should happen next.

See [PRODUCT_POSITIONING.md](PRODUCT_POSITIONING.md).

## Architecture

Public layers:

- Project Map
- Session Runtime
- Project Cockpit
- Worker Roles
- Local Learning
- Release / PR Workflow

See [ARCHITECTURE.md](ARCHITECTURE.md).

## Privacy And Safety

See [PRIVACY.md](PRIVACY.md) and [SAFETY_MODEL.md](SAFETY_MODEL.md).

## Publishing Status

The public alpha is published on branch `release/v1.0.0-alpha.1` with tag `v1.0.0-alpha.1`.

This repository does not assume a `main` branch. See [PUBLISHING.md](PUBLISHING.md), [BRANCHING.md](BRANCHING.md), and [POST_LAUNCH_STATUS.md](POST_LAUNCH_STATUS.md) before changing release branches or the GitHub default branch.

## Alpha Status

This is `v1.0.0-alpha.1`, a public alpha. It is useful for local project operation and release preparation, but it does not create remote pull requests, push branches, deploy systems, or replace human review.

See [RELEASE_NOTES.md](RELEASE_NOTES.md) and [ROADMAP.md](ROADMAP.md).
