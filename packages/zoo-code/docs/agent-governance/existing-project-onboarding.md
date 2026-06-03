# Existing Project Onboarding

Use Project Bootstrap when a repository already exists and should be prepared for Zoo Governance.

The bootstrap scan is read-only for business code. It writes governance artifacts under `.zoo-agent/` and, when applied, drafts local rule files as `.new` or `.patch` files instead of overwriting existing project files.

## Steps

1. Open the project root.
2. Run `Agent: Bootstrap Project`.
3. Review `.zoo-agent/bootstrap-report.md`.
4. Apply safe files only after review.
5. Commit bootstrap files if desired.
6. Start with a small Level 0/1 task.

If test commands, entrypoints, or stack details cannot be detected, they remain `unknown`.
