---
description: Create or check the project charter without entering coding.
argument-hint: <project mission or charter update>
mode: agent-orchestrator
---

Create, update, or check the project charter layer:

- `.zoo-agent/project-charter.json`
- `docs/project-charter.md`

Use `scripts/init-project-charter.py` for creation and `scripts/check-project-charter.py` for validation. Do not modify business code. Do not read secrets. Do not overwrite an existing charter unless the user explicitly asks for an update.

The charter must clarify mission, target users, product goals, technical goals, non-goals, success criteria, quality bar, architecture principles, data/security constraints, risk tolerance, human gates, fallback/abort conditions, decision owners, and open questions.
