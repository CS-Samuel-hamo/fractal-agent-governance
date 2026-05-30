---
name: failure-postmortem
description: Analyze an agent failure, classify root cause, identify missed governance controls, and propose evidence-bound corrections to rules, skills, templates, or review gates.
version: 3.6.0
scope: global
applies_to: agent-curator
last_updated: 2026-05-30
deprecated_by: ""
---

# Failure Postmortem Skill
Use after a task fails, reviewer finds a major omission, user corrects agent behavior, or branch state drifts.

## Procedure
Record event, classify failure, identify root cause, choose intervention, produce postmortem and Rule Change Proposal.

## Output
```markdown
## Failure Postmortem
- event_id:
- task_id:
- branch_id:
- failure_class:
- evidence:
- root_cause:
- missed_control:
- proposed_intervention:
- regression_prompt_or_check:
- rollback_plan:
```
