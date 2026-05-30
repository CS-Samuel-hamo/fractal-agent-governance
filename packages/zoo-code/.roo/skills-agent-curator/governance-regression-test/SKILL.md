---
name: governance-regression-test
description: Create regression prompts and checklist assertions that verify whether a governance rule would prevent a previously observed agent failure.
version: 3.6.0
scope: global
applies_to: agent-curator
last_updated: 2026-05-30
deprecated_by: ""
---

# Governance Regression Test Skill
Use after adding or modifying governance rules.

## Regression Test Types
Prompt regression, checklist regression, static governance validation, branch protocol regression.

## Output
Failure event, regression type, prompt/check, expected agent behavior, pass condition, owner mode.
