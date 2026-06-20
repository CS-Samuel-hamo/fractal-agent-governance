# Changelog

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
