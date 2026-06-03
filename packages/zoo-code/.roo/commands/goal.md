---
description: Create or update a v3.6 goal contract without entering coding.
argument-hint: <goal statement>
mode: agent-orchestrator
---

Create or update `.zoo-agent/goals/<goal-id>.json` using `scripts/init-goal-contract.py`. Include root goal, user intent, business outcome, technical outcome, non-goals, assumptions, constraints, success/failure criteria, abort conditions, risk tolerance, quality bar, max depth, max loop budget, human gate requirement, fallback policy, project-charter path, charter alignment, owner, and timestamps. Do not modify business code. If the goal conflicts with `.zoo-agent/project-charter.json` or `docs/project-charter.md`, stop for GPT planner or user decision.
