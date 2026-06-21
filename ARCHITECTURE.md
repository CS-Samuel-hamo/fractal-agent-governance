# Architecture

Agent Runtime is a local AI Project Operator. The public architecture is organized around product layers, not provider-specific tools.

```text
User
  -> CLI
  -> Project Map
  -> Session Runtime
  -> Worker Roles
  -> Project Cockpit
  -> Release / PR Pack
```

## Project Map

The Project Map records:

- project type
- main goal
- modules
- capabilities
- risks
- next actions
- evidence

The map is stored locally under `.zoo-agent/`. Low-confidence areas stay marked as unknown instead of being treated as facts.

## Session Runtime

Sessions let the product keep moving a project over time.

Session state includes:

- current goal
- status
- current and next action
- checkpoints
- digest
- recovery availability

The user sees simple states such as active, paused, completed, or needs attention.

## Project Cockpit

The Cockpit is a static local HTML page generated from local artifacts. It shows:

- project overview
- current session
- project map
- next actions
- attention required
- recovery status
- release and PR readiness
- local learning insights when available

It does not require a local server or external CDN.

## Worker Roles

Workers are execution options such as:

- Local Scanner
- Code Worker
- Test Worker
- Dry-run Worker
- Mock Worker

Codex, Claude Code, local tools, mock, and dry-run modes fit behind worker roles. The product remains the Project Operator, not any single worker.

## Local Learning

Local learning stores structured summaries from previous local artifacts. It can suggest next-action priority, release readiness patterns, common blockers, and worker preferences.

It does not upload code, save raw source, save raw worker logs, or read secrets.

## Release / PR Workflow

The release workflow generates local artifacts:

- Git context
- readiness report
- PR plan
- PR draft
- release notes draft
- changelog draft
- release action plan

It does not call GitHub, push, merge, create branches, create remote PRs, or deploy.

## Local Artifacts

Runtime artifacts live under `.zoo-agent/`, which should stay ignored by git. Public demo artifacts use `examples/demo_project/demo_artifacts/` instead.
