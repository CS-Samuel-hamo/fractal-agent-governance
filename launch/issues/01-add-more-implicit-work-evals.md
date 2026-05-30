# Add more implicit work discovery evals

Labels: `good first issue`, `eval`, `docs`

## Goal

Add more toy eval cases for tasks where a small explicit request implies broader engineering work.

## Suggested Cases

- Add a public API field.
- Rename an internal DTO field.
- Change default sort behavior.
- Add a config option that affects tests and docs.

## Acceptance Criteria

- Each case is toy data only.
- Each case includes expected obligations, surfaces, routing, gates, forbidden actions, and scoring.
- `python scripts/validate-open-source-package.py` passes.

## Non-goals

- Do not include real project logs.
- Do not include customer or company data.
