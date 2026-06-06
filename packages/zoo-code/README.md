# Zoo Code Agent Governance Kit v0.3.12 Implementation Delivery Kernel

This package contains the Zoo Code adapter. Install it globally; it is not copied into business repositories.

Reload VS Code / Zoo Code after installation. Configure provider profiles separately in the local tool UI; this installer does not install API keys.

v0.3.12 adds the Implementation Delivery Kernel. The default `/agent-run`
entrypoint now treats implementation work as delivery work: plans must terminate
into implementation queue items, ready code/test/config leaves can be promoted
to Codex task packs, and coding tasks cannot be completed with docs-only output
unless they are explicitly classified as non-coding.

The package keeps the project bootstrap, integrated governance board,
task-board/runtime layer, Codex CLI worker bridge, parallel safety checks,
governance closure gates, active resource-lock acquisition/release, and richer
AI-native run summaries from earlier releases. It defines source-of-truth
hierarchy, project charter, project-level `TASKS.md`, `current-run.json`,
three-stage Task Board Apply, resume safety checks, project architecture maps,
resource locks, branch schedule denial reasons, aggregation diagnostics, and
safer Stop/Progress/Redirect/Resume flow.

It integrates:

- Zoo Boomerang Tasks, custom modes, skills, slash commands, worktrees, checkpoints, diagnostics, codebase indexing, and API/sticky model profiles
- goal contract, run-ledger, artifact-graph, project-charter, project-profile, project-map, architecture-boundaries, obligation-ledger, governance intensity, fractal branch tree, worktree scheduling, path locks, checkpoints, diagnostics, quality gate, reviews, parent aggregation, merge queue, metrics, and lessons

Do not copy the full kit into business repositories. Install globally with:

```powershell
python scripts/install-global-zoo-agent-kit.py --dry-run
python scripts/install-global-zoo-agent-kit.py
```

`/agent-run` is the main workflow bus. `/implement` is the explicit delivery
shortcut for turning plans, branches, or task-board items into an implementation
queue and Codex task packs. Other slash commands are control-plane or
evaluation tools.

## Implementation Delivery

Use `/agent-run` normally. For implementation-heavy work, use either direct
conversation through `/agent-run` or the explicit shortcut:

```text
/implement <current goal or run id>
```

Delivery artifacts:

- `.zoo-agent/runs/<run-id>/implementation-queue.json`
- `.zoo-agent/runs/<run-id>/implementation-queue.md`
- `.zoo-agent/runs/<run-id>/codex-tasks/<task-id>/`
- `.zoo-agent/runs/<run-id>/code-delivery-gate.json`
- `.zoo-agent/runs/<run-id>/code-delivery-gate.md`

High-risk actions still require separate explicit authorization: secret reads,
`.env` reads, provider probes, data updates, cache mutation, dependency
install/rebuild, merge, push, deploy, release, destructive cleanup, and
production data migration.

## Runtime Backbone

`Goal -> Run -> Project Context -> Obligations -> Branch Tree -> Worktree Schedule -> Execution -> Evidence -> Gates -> Review -> Parent Aggregation -> Merge Queue -> Integration -> Metrics -> Lessons`

## Boomerang vs Fractal

Zoo Boomerang delegates subtasks and returns summaries. Fractal governance adds controlled recursive decomposition, branch contracts, `needs_decomposition`, max_depth, loop budgets, owned paths, worktree scheduling, path locks, parent aggregation, merge queue, fallback, and lessons.

## Rollback

Restore from `~/zoo-global-agent-kit/backups/global-before-v3.8.1-*` or `~/.roo/backups/zoo-agent-kit-v3.8.1-*` by restoring `~/.roo`, global `custom_modes.yaml`, and local launcher extension directories.

## Move CODEX_HOME to D Drive

Codex CLI stores local state in `CODEX_HOME`, including config, auth, logs, sessions, skills, and cache. Do not commit this directory to Git, do not copy it into business repositories, and do not print auth/token/config contents.

When the C drive is low on space, use a D drive state directory:

```powershell
New-Item -ItemType Directory -Force -Path D:\AI_DEV\codex_home
[Environment]::SetEnvironmentVariable("CODEX_HOME", "D:\AI_DEV\codex_home", "User")
$env:CODEX_HOME = "D:\AI_DEV\codex_home"
```

The Codex worker also supports an explicit override:

```powershell
python scripts\run-codex-worker.py `
  --task-dir "<task-dir>" `
  --workspace "<worktree>" `
  --sandbox workspace-write `
  --codex-home D:\AI_DEV\codex_home
```

The worker points `TMPDIR`, `TMP`, and `TEMP` at the current task pack `.codex-tmp` directory so temporary files stay inside the task-allowed area instead of polluting the worktree root.

Restart PowerShell, VS Code, Zoo Launcher, and Codex App after changing the user-level environment variable.
