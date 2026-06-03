---
name: governed-boomerang-pipeline
description: Run the repository's governed 5-role pipeline by delegating to planner, executor, reviewer, and integrator modes with explicit contracts and completion summaries.
version: 3.7.0
scope: global
applies_to: agent-orchestrator
last_updated: 2026-05-30
deprecated_by: ""
---

# Governed Boomerang Pipeline

Use this skill when a user asks for a feature, refactor, bug fix, migration, or project-management change that should not be handled as a single local coding task.

## Phase selection

Default order:

1. `agent-planner` creates the implementation contract.
2. `agent-planner` creates or updates branch/task state and decomposition when Level 3+ requires fractal planning.
3. `agent-executor` implements the approved contract.
4. `agent-reviewer` reviews the diff and evidence.
5. `agent-integrator` merges or prepares integration only after approval.
6. `agent-integrator` updates governance only after a failure event or recurrence and only with regression evidence.

## Mandatory transition gates

- Planner -> Executor requires a complete implementation contract.
- Executor -> Reviewer requires completion evidence, changed files, tests run, and unresolved risks.
- Reviewer -> Integrator requires verdict `APPROVE` or `APPROVE_WITH_MINOR_FIXES`.
- Reviewer -> Integrator governance curation requires a documented event when a process defect or repeated miss is detected.

## Child summary schema

Every child must finish with:

```markdown
## Completion Summary
- phase:
- outcome: success | partial | blocked | failed
- artifacts:
- changed_files:
- checks_run:
- acceptance_mapping:
- unresolved_risks:
- next_recommended_phase:
```

## Failure handling

If a child returns partial/blocked/failed, do not continue the happy path. Either:

- delegate a remediation subtask to the same specialist mode;
- ask planner to revise the contract;
- ask integrator to create a governance event and regression rule;
- stop and report the blocker.
