# Skill Evolution Policy

Skills evolve only from lesson records or approved governance proposals. A skill change must identify trigger event, failure type, before behavior, expected new behavior, regression prompt, regression check, rollback plan, owner, and approval.

## Promotion Rules
- Single low-risk failure: event only.
- Same failure twice: lesson candidate.
- Same failure three times or high severity: rule/skill/script proposal.
- Machine-detectable problem: prefer script/gate.
- Operational workflow problem: prefer skill.
- High-level behavioral constraint: prefer rule.
- Project fact: project profile or local rule.
- Architecture tradeoff: ADR.
- Security, permissions, PII, or payment: GPT and human approval required.

DeepSeek may draft lesson and skill-change proposals. GPT curator approves. Approved changes still require governance regression and validate/dry-run before install.
