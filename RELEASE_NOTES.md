# Release Notes

## 1.0.5-alpha.7 Non-Git Apply Codex Trust Check Patch

This patch fixes the state where Codex was available, but a prompt-only project
still returned `DRY_RUN_COMPLETE` after `--apply`.

### Fixed

- Non-Git workspaces now automatically pass Codex's git repo check bypass flag
  during bounded local execution.
- Actual execution failures that fall back to dry-run are now reported as
  `BLOCKED`, not `DRY_RUN_COMPLETE`.
- One-off `agent "<task>" --apply` now returns `mode: blocked` when no delivery
  happened, instead of implying that apply succeeded.

### Validation

- Added regression coverage for non-Git Codex command construction.
- Added regression coverage for actual-failure dry-run fallback verdicts.
- Re-ran intent-first seed bootstrap, product alpha, worker doctor, real worker
  adapter hardening, and starter pack checks.

## 1.0.5-alpha.6 Windows Codex Worker Resolution Patch

This patch fixes the real local cause behind `codex CLI permission denied` on
Windows/Anaconda installs.

### Fixed

- Codex worker detection now prefers `codex.cmd`, `codex.exe`, or `codex.bat`
  on Windows instead of invoking the extensionless `codex` shim.
- Actual Codex execution uses the same resolved command as the health check.
- Backend health and worker doctor now agree on Codex availability.
- Agent and pipeline subprocesses now force UTF-8 Python output so Chinese tasks
  do not fail on GBK console encoding.

### Validation

- `agent workers --doctor` now reports actual code execution as available when
  `codex.cmd --version` succeeds.
- Chinese research workflow preview completes without GBK output failure.
- Re-ran worker doctor, real worker adapter hardening, intent-first seed
  bootstrap, product alpha, product surface hardening, local scanner, and
  starter pack checks.

## 1.0.5-alpha.5 Bounded Docs Apply Diagnostics Patch

This patch fixes a real Chinese prompt-only project failure where a bounded
documentation edit was blocked with an unclear JSON result.

### Fixed

- Chinese tasks such as extending `docs/research_workflow.md` from
  `project_beginning_prompt.md` are now recognized as bounded documentation
  edits instead of big/governed project work.
- `--apply` now checks whether the selected actual execution worker is
  available before entering the pipeline.
- When Codex execution is unavailable, the CLI now reports a clear user-facing
  reason such as `actual execution worker unavailable: codex CLI permission
  denied; run agent workers --doctor`.
- Windows debug/status output is more tolerant of Unicode text.

### Validation

- Added regression coverage for Chinese research workflow edits staying on the
  fast/small path with an `actual_allowed` plan.
- Re-ran intent-first seed bootstrap, product alpha, product surface, worker
  doctor, real worker adapter hardening, local scanner, and starter pack checks.

## 1.0.5-alpha.4 Preview Job Supersede Patch

This patch fixes the confusing state where a preview-only seed starter job could block a user's next natural-language goal with `Existing job found`.

### Fixed

- Preview-only seed starter jobs can now be superseded by a new goal.
- Genuinely active jobs are still protected from accidental overwrite.
- Users no longer need to run `agent stop` just to move past a no-op starter preview.

### Validation

- Added regression coverage for replacing an all-existing-docs seed preview with a new project goal.

## 1.0.5-alpha.3 Partial Starter Docs Patch

This patch makes seed prompt execution match the expected user behavior: keep existing starter docs and create only the missing trusted docs.

### Changed

- Existing starter docs are skipped instead of causing the whole starter action to become preview-only.
- Missing trusted docs are still created when at least one starter target is absent.
- Preview-only is now reserved for the case where all starter doc targets already exist.

### Safety

- Existing files are not overwritten.
- Only trusted starter docs are eligible: `README.md`, `docs/project_plan.md`, and `docs/research_workflow.md`.
- The flow still does not execute shell commands, read secrets, push, merge, deploy, or generate final paper content.

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
