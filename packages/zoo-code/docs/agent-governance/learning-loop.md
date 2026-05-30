# Learning Loop

Governance evolution follows this closed loop:

`Event -> Lesson -> Candidate Change -> Regression -> Approval -> Install -> Metrics -> Deprecation`

The loop is constrained. Events and postmortems can create lesson candidates, but they cannot directly rewrite global rules, skills, commands, scripts, model routing, security policy, or human exception policy.

## States
1. Event: failure, postmortem, repeated reviewer finding, gate false positive, or operational incident.
2. Lesson: structured record under `.zoo-agent/lessons/`.
3. Candidate Change: proposed rule, skill, script, local rule, project profile update, or ADR.
4. Regression: prompt/check proving before behavior and expected new behavior.
5. Approval: GPT curator approval; human approval for security, human exception, and model routing changes.
6. Install: run validate, dry-run, target-path safety check, then install.
7. Metrics: append learning metrics and skill invocation outcomes.
8. Deprecation: stale, harmful, or irrelevant assets become candidates for removal or replacement.

## Hard Gates
No regression means no installation. DeepSeek curator-draft may extract lessons and draft proposals only. GPT curator approves proposals. Human approval is required for security/human-exception/model-routing changes.
