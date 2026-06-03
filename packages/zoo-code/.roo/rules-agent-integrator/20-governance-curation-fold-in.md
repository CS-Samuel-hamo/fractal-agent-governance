# Integrator Governance Curation Fold-In

Integrator absorbs the former curator and curator-draft capabilities for user-visible mode purposes.

Governance evolution may happen only from evidence:

- review finding
- failed task
- repeated failure
- incident or postmortem
- user correction
- governance regression result

Before installing a governance change, Integrator must require:

- source event or failure evidence
- failure type
- smallest effective asset choice
- expected behavior change
- regression prompt or machine-checkable regression
- rollback plan
- approval authority
- `python scripts/validate-zoo-agent-kit.py`
- installer dry-run when global installation is involved

Promote only the smallest effective change. Prefer script/gate for machine-detectable failures, skill for workflow execution, rule for high-level behavior, project-local rule for project facts, and ADR for architecture tradeoffs.

Never weaken safety, review, version, model routing, human exception, or data-source gates without explicit human approval.
