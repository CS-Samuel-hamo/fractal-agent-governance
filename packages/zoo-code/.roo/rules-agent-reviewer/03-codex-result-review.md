# Codex Result Review

Reviewer must treat Codex CLI output as worker evidence, not final truth.

Review:

- `result.json` and `result.md`
- scope guard pass or fail
- changed files against allowed and denied files
- acceptance criteria evidence
- test output or documented blocker
- architecture, public API, dependency, security, auth, PII, payment, schema, and migration drift

Any denied file change, unapproved architecture drift, missing scope guard, or missing acceptance evidence is at least MAJOR and may be BLOCKER.
