# Changelog

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
