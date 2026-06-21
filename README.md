# AI Project Operator

Give it a project. It keeps moving it forward.

Agent Runtime is a local-first AI Project Operator. It builds a project map, starts a durable work session, chooses the next project-level action, coordinates available AI workers, shows progress in a local Cockpit, and prepares release or PR-ready artifacts.

It is not a Codex wrapper, a Claude Code replacement, a generic AI coding CLI, or a GitHub bot. Codex, Claude Code, local scanner, mock, and dry-run modes are workers. The product is the project operator layer that keeps the project moving.

## Quick Demo

```bash
agent cockpit
agent start "prepare this project for public release"
agent status
agent release
agent pr
```

The public path is:

1. Map the project.
2. Start an autopilot session.
3. Watch progress in Cockpit.
4. Continue, stop, or undo.
5. Generate a local release and PR pack.

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

```bash
agent "<task>"
agent "<task>" --preview
agent "<task>" --apply
agent start "<project goal>"
agent status
agent continue
agent stop
agent undo
agent cockpit
agent release
agent pr
```

See [CLI_REFERENCE.md](CLI_REFERENCE.md) for details.

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

## Alpha Status

This is a public alpha. It is useful for local project operation and release preparation, but it does not create remote pull requests, push branches, deploy systems, or replace human review.

See [RELEASE_NOTES.md](RELEASE_NOTES.md) and [ROADMAP.md](ROADMAP.md).
