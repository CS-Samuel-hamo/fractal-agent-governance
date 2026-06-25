# Changelog

## v1.1.0-session-cockpit

- Added undo apply: `agent undo --apply --yes` now performs git checkout to revert files.
- Added undo preview: shows changed files, diff stat summary, and checkpoint commit hash.
- Fixed session recovery: cockpit sync failure no longer blocks session continuation.
- Added session diagnostics: lock PID/age info and `--verify` mode for file integrity checks.
- Enhanced cockpit timeline: merged chronological sort (up to 20 entries), duration, file counts.
- Enhanced attention panel: severity badges (blocking/warning/info), related modules, file paths.
- Added pyproject.toml with ruff, pytest, and coverage configuration.
- Split agent.py from 3072 lines into 5 focused modules: `agent_utils.py`, `agent_commands.py`, `agent_commands_ux.py`, `agent_commands_release.py`.
- Reorganized root documentation: 44 files → 22 at root, moved to `docs/{releases,alpha,planning,feedback}/`.
- Unified code style: ruff format + lint applied to all 336 Python files.
- Added test infrastructure: `conftest.py`, `test_helpers.py`, pytest configuration.
- Added CI: `.github/workflows/ci.yml` for lint, format, and test gates.
- Added pre-commit hooks for automated quality checks.

## v1.0.0-alpha.2

- Packaged 1.0.6, 1.0.7, and 1.0.8 post-alpha patches into a new public alpha source release.
- Updated public version metadata from `v1.0.0-alpha.1` to `v1.0.0-alpha.2`.
- Kept the main product path focused on `agent "<goal>"`, `agent`, `agent do "<task>"`, `agent cockpit`, and `agent undo`.
- Preserved local-first safety guarantees: no automatic push, merge, deployment, remote PR creation, `.env` reading, or API key storage.

## 1.0.8-interaction-closure-new-user-guidance

- Added beginner-friendly interaction summaries with `Result`, `Where you are`, `What changed`, `How to check`, `Next`, `If this is not what you wanted`, and `Details`.
- Added first-run Welcome guidance so an empty project explains how to start with `agent "<goal>"`, `agent do "<task>"`, or `agent cockpit`.
- Added `agent do "<task>"` as the independent one-off path for explanations, reviews, examples, and bounded edits that should not replace the current project goal.
- Improved `agent continue` recommendations so it is only the primary next step when a real queued action exists.
- Surfaced Project Map, landing proof, project rules, and logic checks in `Details` instead of forcing new users to understand internal concepts first.
- Updated README, Quickstart, and CLI reference around the AI Project Operator interaction loop.

## 1.0.7-unified-prompt-execution-entry

- Made `agent "<prompt>"` the primary user entry for understanding a prompt, executing one safe step, and reporting progress.
- Added prompt intent routing for single-step edits, seed prompt execution, project goals, and unsafe requests.
- Allowed preview-only or no-delivery jobs to yield to a new explicit prompt while preserving active-job protection.
- Kept `--preview` and `--apply` as compatibility flags instead of the main user mental model.
- Standardized normal output around project progress instead of backend or worker details.

## 1.0.6-timeout-aware-worker-failover-docs-apply

- Added bounded documentation writing for safe `.md` / `.txt` updates under README or `docs/`.
- Added timeout-aware execution handling so failed actual execution does not report `DRY_RUN_COMPLETE` as success.
- Added optional remote OpenAI worker adapter plumbing with API keys read only from environment variables and never written to artifacts.
- Improved worker doctor and execution diagnostics for Codex timeout, Windows sandbox, Unicode path, and unavailable-worker cases.
- Added regression coverage for safe docs apply, no-overwrite behavior, secret/file boundary checks, and no API key leakage.

## 1.0.5-alpha.7-non-git-apply-codex-trust-check

- Added automatic `--skip-git-repo-check` for Codex execution in non-Git workspaces, preserving support for new/prompt-only projects.
- Fixed verifier behavior so actual execution failures that fall back to dry-run are reported as blocked, not `DRY_RUN_COMPLETE`.
- Fixed one-off `agent "<task>" --apply` output so non-delivery returns `mode=blocked` instead of a misleading apply result.
- Added regression coverage for non-Git Codex command construction and actual-failure fallback verdicts.

## 1.0.5-alpha.6-windows-codex-worker-resolution

- Fixed Windows Codex CLI worker resolution by preferring `codex.cmd` / `codex.exe` over the extensionless Anaconda `codex` shim.
- Aligned Codex worker health, backend health, and actual execution adapter command resolution.
- Forced UTF-8 child process output for agent/pipeline subprocesses to avoid GBK failures on Chinese tasks.
- Confirmed `agent workers --doctor` reports actual code execution as available when `codex.cmd --version` succeeds.

## 1.0.5-alpha.5-bounded-doc-apply-diagnostics

- Fixed Chinese bounded documentation edits such as extending `docs/research_workflow.md` from `project_beginning_prompt.md` being misclassified as big/governed tasks.
- Added apply preflight diagnostics so unavailable actual execution workers now report a clear reason such as `codex CLI permission denied`.
- Hardened Windows debug/status output against Unicode encoding failures.
- Added regression coverage for Chinese research workflow document edits staying on the fast/small execution path.

## 1.0.5-alpha.4-preview-job-supersede

- Allowed a preview-only seed starter job to be superseded by a new natural-language goal.
- Kept protection for genuinely active jobs, while avoiding the confusing `Existing job found` block after no-op starter previews.
- Added regression coverage for replacing an all-existing-docs seed preview with a new project goal.

## 1.0.5-alpha.3-partial-starter-docs

- Changed seed prompt starter docs behavior from all-or-preview to create-missing-only.
- Existing starter docs are preserved; missing trusted docs are created.
- Preview-only is now used only when all starter doc targets already exist.
- Added regression coverage for partial existing starter docs.

## 1.0.5-alpha.2-starter-docs-completion

- Fixed seed prompt starter actions that could loop as preview-only after `agent continue`.
- Added a safe internal starter docs writer for `README.md`, `docs/project_plan.md`, and `docs/research_workflow.md`.
- Marked completed starter docs jobs as `Completed` instead of `Needs attention`.
- Ensured `agent continue` after completion is harmless and does not overwrite starter docs.
- Added regression coverage for one-time starter docs creation and no-overwrite behavior.

## 1.0.5-intent-first-seed-bootstrap

- Added safe seed prompt discovery for prompt-only projects.
- Added intent-first fallback when Project Map has no executable next action.
- Added seed prompt evidence and seed prompt project module support.
- Added starter docs actions for `README.md`, `docs/project_plan.md`, and research-oriented `docs/research_workflow.md`.
- Improved Job Inbox clarity so `blocked zone` is always accompanied by reason, evidence, risk, and next-step guidance.
- Added fixture tests for seed prompt bootstrap, safety filtering, dangerous goals, and preview-only existing-file behavior.

## 0.8.3-alpha

- Added product-facing CLI UX for goal -> run -> result.
- Added `agent backend list`, `agent backend switch <name>`, and `agent backend health`.
- Added product docs: install, quickstart, examples, architecture, CLI reference, backend plugins, and product mind model.
- Added product alpha acceptance test coverage.
- Kept runtime core backend-agnostic and Codex as a replaceable backend plugin.

## 0.8.2-semantic-decoupling-runtime-engine

- Removed runtime-facing Codex semantic coupling from execution result schema and verifier logic.
- Standardized backend-neutral fields such as `backend_type`, `backend_status`, and `backend_returncode`.
- Added semantic decoupling tests.

## 0.4.0-local-alpha

- Added first-class existing project and new project onboarding.
- Added `agent --version`.
- Hardened interactive natural-language CLI usage.
- Added bootstrap profile, readiness, report, and lock artifacts.
- Added conservative parallel independence checks and denial reasons.
- Added fast path minimal report timing metrics.
- Added rollback dry-run safety plan behavior.
- Added local alpha acceptance test coverage.

## 0.3.x

- Introduced CLI-first runtime routing.
- Added goal, loop, classifier, fast, parallel, governed paths.
- Added Codex CLI worker bridge and governance closure scripts.
