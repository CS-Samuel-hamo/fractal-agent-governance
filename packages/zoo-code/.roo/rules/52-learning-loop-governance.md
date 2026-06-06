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

## v0.3.9 Learning Noise Reduction

Do not learn on every step. Do not write a lesson for every success. Do not update a skill for every ordinary failure.

Create a lesson candidate only for scope violation, test failure not fixed after retry, review BLOCKER or MAJOR, repeated same failure type, human correction, architecture violation, Codex changed denied files, or Codex inferred architecture change without approval.

Machine-detectable issues should become script or gate checks before prompt-heavy guidance. Low-risk one-time issues are recorded as events only.

## Implementation Delivery Bias

Do not learn merely because product documentation volume increased. Do not add
large rules after one doc-only drift. If two consecutive coding tasks produce
only docs, create a lesson candidate `delivery_bias_detected`. If three
consecutive coding tasks show the same failure, curator-draft may propose a
rule, skill, or script change.

Prefer machine-checkable gates over longer prompts:

- `delivery_bias_doc_only`
- `implementation_queue_missing`
- `local_optimization_loop`
- `root_goal_drift`
- `product_doc_overproduction`
- `codex_task_pack_not_generated`

Local optimization deferred to follow-up does not trigger a lesson unless it
repeatedly blocks the root goal.
