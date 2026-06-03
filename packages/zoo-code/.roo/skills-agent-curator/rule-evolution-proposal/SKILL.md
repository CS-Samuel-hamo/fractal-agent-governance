---
name: rule-evolution-proposal
description: Convert a postmortem into a minimal, reviewable governance patch affecting rules, skills, templates, review checklists, or model-routing policy.
version: 3.6.0
scope: global
applies_to: agent-integrator
last_updated: 2026-05-30
deprecated_by: ""
---

# Rule Evolution Proposal Skill
Use when a failure postmortem shows the same mistake may recur.

## Patch Selection Heuristic
Before-edit failure -> planner/task template. Coding failure -> executor rule/skill. Escaped defect -> reviewer checklist. Branch ownership failure -> branch-agent contract. Wrong model -> model-routing matrix. Version isolation failure -> worktree/checkpoint playbook.

## Guardrails
Do not add generic admonitions. Every rule must force a concrete action, output field, search, gate, or test.
