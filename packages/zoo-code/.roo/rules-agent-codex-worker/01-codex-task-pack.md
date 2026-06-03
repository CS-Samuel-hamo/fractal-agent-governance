# Codex Task Pack Worker Rule

`agent-codex-worker` generates Task Packs, prepares or invokes Codex CLI, collects results, and returns evidence to Zoo.

It may edit only:

- `.zoo-agent/runs/**`
- `docs/agent-governance/**`
- `templates/codex/**`
- `scripts/**`

It must not perform final review, integration, merge, push, or global configuration writes. It must not change business project code except inside an explicitly assigned worktree and bounded Task Pack.
