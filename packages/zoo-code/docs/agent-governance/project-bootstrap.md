# Project Bootstrap

Project Bootstrap adds one-click setup for existing and new projects.

## Existing Project Flow

1. Open project root.
2. Run `Agent: Bootstrap Project` or `/agent-bootstrap`.
3. Review `.zoo-agent/bootstrap-report.md`.
4. Apply safe bootstrap files.
5. Commit bootstrap files if desired.
6. Start a Level 0/1 task.

## New Project Flow

1. Open empty folder.
2. Run `Agent: Bootstrap Project`.
3. Enter project goal/stack if known.
4. Generate governance shell.
5. Commit initial governance shell.
6. Ask Zoo/GPT to plan first tasks.
7. Give leaf tasks to Codex Worker.

Bootstrap never reads secrets and never writes business code.
