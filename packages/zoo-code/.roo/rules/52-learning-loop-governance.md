# Learning Loop Governance

Governance assets evolve only through `Event -> Lesson -> Candidate Change -> Regression -> Approval -> Install -> Metrics -> Deprecation`.

Events and postmortems may create lesson candidates. They must not directly rewrite global rules, skills, commands, scripts, local project rules, model routing, security policy, or human exception policy.

Required promotion gates:
- single low-risk failure: event only
- same failure twice: lesson candidate
- same failure three times or high severity: candidate change proposal
- machine-detectable issue: prefer script/gate
- workflow issue: prefer skill
- high-level behavior: prefer rule
- project fact: project-profile/local rule
- architecture tradeoff: ADR
- security/permissions/PII/payment: GPT and human approval required

No governance regression means no installation. DeepSeek may draft lessons/proposals only. GPT curator approves. Human approval is required for security, human exception, and model routing changes.
