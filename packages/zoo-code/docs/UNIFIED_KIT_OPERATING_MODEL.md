# Unified Kit Operating Model

The global package and governance package should be installed as one physical
kit while keeping logical boundaries.

## One Physical Kit

Default installed location:

```text
$env:USERPROFILE\.roo\agent-governance-kit
```

The one-touch setup entrypoint is:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\setup_zoo_agent.py `
  --project "<project>" `
  --mode auto
```

This single command:

1. validates the source starter pack;
2. syncs global `.roo` command/rule/skill entrypoints;
3. syncs the installed `agent-governance-kit`;
4. bootstraps or repairs the target project;
5. writes one setup report under `.zoo-agent/`;
6. writes architecture compatibility and rollback artifacts.

## Logical Layers

The unified kit keeps these boundaries:

- global entrypoints: `.roo/commands`, `.roo/rules`, `.roo/skills-*`
- governance runtime: Level 0-4 routing, risk register, task board, review and
  integration gates
- project bootstrap: project facts, source-of-truth resolver, compatibility
  report, migration and rollback anchors
- worker bridge: Codex task packs, isolated worktrees, harness verification,
  result collection, and run summary
- governance closure: task-board consistency, risk register, quality gate,
  active resource locks, and serial merge queue processing contracts
- field-feedback layer: real-project lessons converted into compatibility
  checks, summary fields, rules, and the integration matrix in
  `docs/FIELD_FEEDBACK_INTEGRATION_MATRIX.md`
- Vibe Coding cross-validation: failure-mode checks for goal understanding,
  execution landing, semantic correctness, dependency state, concurrency,
  progress tracking, side effects, and repeatability

## Setup Rule

For new and existing projects, prefer `agent-setup` first. Use
`agent-bootstrap` only when the global kit is already known to be current and
you only want to refresh one project.

## Closure Rule

A run is not ready to merge or release until all three closure gates are true:

- execution closure: worker executed, or the run is explicitly governance-only;
- evidence closure: reviewer evidence, tests, quality gates, and run JSON agree;
- integration closure: merge queue is processable and final gate authorization
  is recorded.

This keeps global entrypoints, governance state, and project-local evidence from
drifting apart.
