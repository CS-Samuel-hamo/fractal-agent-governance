# Community Posts

## GitHub Repo Description

AI Project Operator: Project Map-backed Autopilot for local project progress.

## Hacker News Style Post

I built an AI Project Operator for local repositories.

Most AI coding tools can do individual tasks, but projects still get messy: missing context, unclear next actions, no durable state, and no simple way to see what changed. Agent Runtime maps the project, starts long-running sessions, shows progress in a local Cockpit, and prepares release / PR drafts locally.

It is not a Codex wrapper or a Claude Code replacement. Codex, Claude Code, and local tools are workers. The product is the project operator.

Feedback wanted: does the Project Map help you understand what the project needs next?

## Reddit / LocalLLaMA / ClaudeAI / OpenAI Community Style Post

I am testing a local-first AI Project Operator.

Positioning: Project-level Autopilot, not task-level coding agent.

The tool keeps a Project Map, runs project sessions, shows a local Cockpit, and generates release / PR drafts. It does not create remote GitHub PRs, call GitHub APIs, push, merge, deploy, or use cloud sync.

I am especially looking for feedback on first-run clarity, Project Map quality, Autopilot next actions, Cockpit readability, and release / PR draft usefulness.

## X / LinkedIn Short Post

Launching a public alpha of Agent Runtime: an AI Project Operator.

Give it a project. It keeps moving it forward.

Project Map-backed Autopilot, local Cockpit, durable sessions, and local release / PR drafts.

Feedback welcome.

## One-paragraph Founder Note

AI coding agents are useful, but project ownership is still messy. Agent Runtime is my attempt at an AI Project Operator: it maps the repo, tracks progress, chooses the next action, coordinates workers, and prepares local release / PR drafts without pushing, merging, or calling GitHub APIs. I am looking for early feedback from builders who want project-level momentum rather than another one-off coding prompt.

## Feedback Request Post

If you try the alpha, please tell me:

- Did the Project Map match your repo?
- Did Autopilot choose a useful next action?
- Did Cockpit explain progress clearly?
- Did release / PR drafts help?
- What confused you in the first five minutes?

Please remove secrets, raw logs, and local absolute paths before sharing artifacts.

## Short Demo Script

```bash
agent cockpit
agent start "prepare this project for public release"
agent status
agent release
agent pr
```
