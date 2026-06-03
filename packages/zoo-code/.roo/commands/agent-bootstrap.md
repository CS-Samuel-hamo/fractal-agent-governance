---
description: Bootstrap an existing or new project for Zoo Governance + Codex CLI Worker.
argument-hint: [existing|new] [optional project goal or stack]
mode: agent-orchestrator
---

# /agent-bootstrap

Bootstrap the current project for Zoo Governance + Codex CLI Worker without changing business code.

## Behavior

1. Detect project type:
   - `existing_git_project`
   - `existing_non_git_project`
   - `empty_new_project`
   - `unknown`
2. For existing Git projects:
   - perform read-only project scan;
   - generate `.zoo-agent/project-profile.json`;
   - generate `.zoo-agent/project-readiness.json`;
   - generate `.zoo-agent/bootstrap-report.md`;
   - generate `.zoo-agent/local-rules-summary.md`;
   - generate or refresh `.zoo-agent/project-map.json`, `.zoo-agent/project-map.md`, and `.zoo-agent/architecture-boundaries.json`;
   - generate or refresh `.zoo-agent/current-run.json` and `.zoo-agent/TASKS.md` as the project-level task board entry for the current run;
   - generate or refresh `.zoo-agent/runs/<run-id>/TASKS.md`, `task-board.json`, `progress.json`, `progress.md`, `progress-tree.md`, and `tasks/<branch>.md` for existing runs that do not already have a human-editable task board;
   - if no run exists, create a bootstrap run with a root planning branch;
   - report missing project charter instead of inventing one; use `/charter` when durable mission, non-goals, quality bar, or human gates are needed;
   - create `AGENTS.md`, `.gitignore`, and `.roo/rules/*.md` when they are missing;
   - leave existing complete local governance files alone;
   - generate `AGENTS.md.new` only when existing `AGENTS.md` is missing minimum agent safety/routing rules and must not be overwritten;
   - generate `.gitignore.agent.patch` only when existing `.gitignore` is missing agent runtime ignore rules;
   - do not modify business code;
   - do not commit.
3. For empty new projects:
   - initialize Git unless disabled;
   - create `README.md`, `AGENTS.md`, `.gitignore`, `.zoo-agent/project-profile.json`, `.zoo-agent/bootstrap-report.md`, `.zoo-agent/project-map.json`, `.zoo-agent/project-map.md`, `.zoo-agent/architecture-boundaries.json`, `.zoo-agent/current-run.json`, `.zoo-agent/TASKS.md`, a first root `TASKS.md` draft, and a bootstrap run task board under `.zoo-agent/runs/<run-id>/`;
   - do not write business modules.
4. For existing non-Git projects:
   - report recommendations;
   - do not run `git init` unless the user explicitly chose new project initialization;
   - do not modify business files.

## Local Command

Run from the project root:

```bash
python ~/.roo/agent-governance-kit/scripts/bootstrap_project.py --project . --mode auto --dry-run
```

Apply safe governance files after reviewing the report:

```bash
python ~/.roo/agent-governance-kit/scripts/bootstrap_project.py --project . --mode auto --apply
```

## Required Output

- Next actions.
- Whether the project is safe for Level 0/1 Codex Worker trial.
- Items requiring user confirmation.
