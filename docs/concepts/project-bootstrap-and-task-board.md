# Project Bootstrap And Task Board

Project bootstrap is the one entry point for onboarding both new and existing projects.

It creates or refreshes lightweight project governance artifacts under `.zoo-agent/` without copying the full global kit into the business repository.

Key project-level files:

- `.zoo-agent/project-charter.json`
- `.zoo-agent/project-profile.json`
- `.zoo-agent/project-map.json`
- `.zoo-agent/architecture-boundaries.json`
- `.zoo-agent/project-readiness.json`
- `.zoo-agent/current-run.json`
- `.zoo-agent/TASKS.md`

`current-run.json` points to the active run. `.zoo-agent/TASKS.md` is the human-editable current task-board entry. Run-local files under `.zoo-agent/runs/<run-id>/` keep machine state and history.

Bootstrap creates missing local behavior files directly. Existing complete files are left unchanged. Existing incomplete files produce `.new` proposals, and existing `.gitignore` files receive `.gitignore.agent.patch` when review is needed.
