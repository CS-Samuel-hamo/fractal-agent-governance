# Release Notes

## 1.0.5-alpha.2 Starter Docs Completion Patch

This patch fixes the post-bootstrap continuation loop discovered in real prompt-only project usage.

### Fixed

- `agent continue` no longer repeats the same seed prompt preview state after a safe starter action is available.
- Safe seed prompt starter actions now create trusted starter docs directly when targets do not already exist.
- Completed starter docs jobs now show `Status: Completed` and `Needs attention: none`.
- Follow-up `agent continue` after completion is harmless and does not overwrite existing starter docs.

### Safety

- The internal starter docs writer can only create `README.md`, `docs/project_plan.md`, and `docs/research_workflow.md`.
- It does not run shell commands, call external workers, access secrets, overwrite files, push, merge, deploy, or generate full paper content.

### Validation

- Added regression coverage for one-time starter docs creation, completed job status, and no-overwrite behavior.

## 1.0.5 Intent-first Seed Prompt Bootstrap Patch

This patch improves first-run behavior for empty or prompt-only projects.

### Added

- Seed prompt discovery for safe root-level or `docs/` `.md` / `.txt` files such as `project_beginning_prompt.md`, `project_prompt.md`, `goal.md`, `brief.md`, `spec.md`, `requirements.md`, `prompt.md`, and `plan.md`.
- Intent-first fallback when Project Map cannot find an executable next action.
- Structured seed prompt evidence and a `Seed prompt project brief` module in Project Map.
- Starter documentation actions for prompt-only projects, including `README.md`, `docs/project_plan.md`, and research-oriented `docs/research_workflow.md`.
- Job Inbox fields for `Reason`, `Evidence`, `Suggested next action`, `Risk level`, `Autopilot`, and `How to continue`.
- Feature flag: `AGENT_ENABLE_INTENT_FIRST_BOOTSTRAP=false` restores the old Project Map-only behavior.

### Safety

- Seed prompts are treated as user intent evidence, not system instructions.
- The starter action does not run scripts, read secrets, overwrite existing files, push, merge, deploy, or fabricate citations/results.
- Dangerous goals such as deleting files, reading `.env`, pushing, merging, production deployment, or database migration remain blocked with a concrete reason.

### Validation

- Added fixture coverage for prompt-only projects, explicit seed files, seed priority, oversized/secret-like seed files, injection attempts, research prompts, existing README preview-only behavior, dangerous goals, and Job Inbox clarity.

## v1.0.0-alpha.1 Public Alpha Release Gate

This release packages Agent Runtime as a public alpha AI Project Operator.

### Added

- VERSION file set to `1.0.0-alpha.1`.
- GitHub release draft for manual publishing.
- Public release checklist for safe manual release.
- Public release gate, package manifest, fresh clone verifier, demo flow verifier, tag preflight, and release report generation.
- Branch-aware publishing notes for the `release/v1.0.0-alpha.1` alpha branch.
- Post-launch remote verification and branch hygiene reports.

### Confirmed

- Public positioning remains AI Project Operator.
- Core differentiation remains Project-level Autopilot, not task-level coding agent.
- Public commands remain focused on task, session, Cockpit, release, and PR draft flows.
- Release and PR workflow remains local draft generation only.
- Published alpha content is verified by release branch, tag, tree equality, and empty file diff.

### Known Limitations

- This release does not create remote GitHub PRs.
- Product release and PR workflows do not call GitHub APIs.
- The public alpha branch and tag were completed with a manual GitHub Git Data API fallback after Git HTTPS push reset; this does not mean a GitHub Release object was created.
- This release does not push, merge, deploy, or create a remote release.
- Claude/local actual execution is not claimed as fully supported unless real local adapters are detected.
- Human review is required before publishing.

## 0.99 Public Alpha Packaging

This alpha packages Agent Runtime as an AI Project Operator.

## Added

- Public positioning: AI Project Operator.
- Public command surface for tasks, sessions, Cockpit, release packs, and PR drafts.
- Public docs for quickstart, CLI, positioning, privacy, safety, demo, roadmap, and architecture.
- Local public alpha audit tooling.
- Safe demo project fixture.

## Changed

- Documentation now emphasizes project-level autopilot instead of task-level coding.
- Codex, Claude Code, local scanner, mock, and dry-run are described as workers, not the product.
- Release and PR flows are presented as local draft generation, not remote publishing automation.

## Known Limitations

- The public alpha does not create remote pull requests.
- It does not push, merge, deploy, or call GitHub APIs.
- Real external worker availability depends on local installation and diagnostics.
- Local learning is advisory and does not train a model.
- Human review remains required before publishing or deploying.

## Not Included

- Cloud sync
- account system
- payment
- plugin marketplace
- VS Code extension
- Electron app
- remote telemetry
