# Zoo Code Agent Governance Kit v3.10 Project Bootstrap + Codex Worker Bridge

This package contains the Zoo Code adapter. Install it globally; it is not copied into business repositories.

v3.10 adds the Codex CLI worker bridge, one-command project bootstrap for new and existing projects, project-level `TASKS.md` and `current-run.json`, safer `AGENTS.md` / local-rule proposal behavior, runtime consistency compatibility for older artifact graphs, and tighter parallel resource-lock checks.

It integrates:

- Zoo Boomerang Tasks, custom modes, skills, slash commands, worktrees, checkpoints, diagnostics, codebase indexing, and API/sticky model profiles.
- Goal contract, run-ledger, artifact-graph, project-charter, project-profile, project-map, architecture-boundaries, obligation-ledger, governance intensity, fractal branch tree, worktree scheduling, path locks, resource locks, checkpoints, diagnostics, quality gate, reviews, parent aggregation, merge queue, metrics, and lessons.
- Codex CLI worker task packs, scope guards, result collection, and executor comparison smoke tests.

Do not copy the full kit into business repositories. Install globally with:

```powershell
python scripts/install-global-zoo-agent-kit.py --dry-run
python scripts/install-global-zoo-agent-kit.py
```

Reload VS Code / Zoo Code after installation. Configure provider profiles separately in the local tool UI; this installer does not install API keys.

`/agent-run` is the main workflow bus. `/agent-bootstrap` is the project onboarding entry point. Other slash commands are control-plane, Codex worker, progress, redirect, or evaluation tools.

## Runtime Backbone

`Goal -> Project Bootstrap -> current-run.json -> TASKS.md -> Run -> Project Context -> Obligations -> Branch Tree -> Worktree Schedule -> Execution -> Evidence -> Gates -> Review -> Parent Aggregation -> Merge Queue -> Integration -> Metrics -> Lessons`

Project-level facts live under `.zoo-agent/`:

```text
.zoo-agent/
  project-charter.json
  project-profile.json
  project-map.json
  architecture-boundaries.json
  project-readiness.json
  current-run.json
  TASKS.md
```

Run-level facts live under `.zoo-agent/runs/<run-id>/`:

```text
run-ledger.json
branch-state.json
task-board.json
TASKS.md
tasks/<branch-id>.md
progress.md / progress.json / progress-tree.md
artifact-graph.json
branch-schedule.json
worktree-map.json
path-locks.json
resource-locks.json
merge-queue.json
```

`TASKS.md` at the project root is the current human-editable task-board entry. The run-local `TASKS.md` is the current run snapshot/archive. `tasks/root.md` is the root branch detail document, not a second global task board.

## Project Bootstrap

Use one operation for new and existing projects:

```powershell
python scripts/bootstrap_project.py --project . --mode auto --apply
```

Bootstrap creates or refreshes project facts, local behavior summaries, readiness reports, run task boards, `.zoo-agent/current-run.json`, and `.zoo-agent/TASKS.md`.

Safety rules:

- Missing `AGENTS.md` is created.
- Existing complete `AGENTS.md` is left unchanged.
- Existing incomplete `AGENTS.md` gets `AGENTS.md.new`.
- Missing `.roo/rules/*.md` files are created.
- Existing rule files are left unchanged.
- Existing `.gitignore` gets `.gitignore.agent.patch` when agent runtime ignore rules are missing.

## Codex Worker Bridge

Codex worker mode is for bounded leaf tasks. Generate a task pack, run Codex inside the assigned workspace/worktree, check scope, and collect the result:

```powershell
python scripts/generate-codex-task-pack.py --run-id <run-id> --task-id <task-id> --objective "<objective>" --allowed-file "src/**" --acceptance "<acceptance>" --test-command "<tests>"
python scripts/run-codex-worker.py --task-dir ".zoo-agent/runs/<run-id>/codex-tasks/<task-id>" --workspace "<worktree>" --sandbox workspace-write --dry-run
python scripts/check-codex-scope.py --task-id <task-id> --tasks ".zoo-agent/runs/<run-id>/codex-tasks/<task-id>/TASKS.yaml"
python scripts/collect-codex-result.py --run-id <run-id> --task-id <task-id> --task-dir ".zoo-agent/runs/<run-id>/codex-tasks/<task-id>" --workspace "<worktree>"
```

Codex workers must not perform final review, integration, merge, push, or global configuration writes.

## Parallel Scheduling

Parallel execution is a safety plan, not automatic background fan-out. After branch contracts exist, run:

```powershell
python scripts/schedule-parallel-branches.py --run-id <run-id> --goal-id <goal-id> --branch-tree <branch-tree.json>
python scripts/generate-resource-locks.py --run-id <run-id>
python scripts/check-parallel-branch-safety.py --run-id <run-id>
```

The scheduler writes `branch-schedule.json`, `worktree-map.json`, `path-locks.json`, `merge-queue.json`, `parent-aggregation-matrices.json`, `parallel-metrics.json`, and `parallel-execution-report.md`.

Parallel coding requires non-overlapping owned paths, declared shared paths, stable provides/consumes contracts, low/medium risk, worktree isolation, path locks, resource locks, checkpoints, and GPT planner/orchestrator approval. Final integration is always serialized through merge queue and parent aggregation.

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

## Validation

Run package validation before publishing or installing:

```powershell
python scripts/validate-zoo-agent-kit.py
python scripts/smoke-test-codex-worker.py
python scripts/run-evals.py --suite parallel-branch
```
