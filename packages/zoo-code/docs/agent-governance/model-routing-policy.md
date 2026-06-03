# Hybrid GPT/DeepSeek Routing Policy

The visible Zoo modes are reduced to five:

- agent-orchestrator
- agent-planner
- agent-executor
- agent-reviewer
- agent-integrator

Specialist behavior is folded into those modes:

- project profiler and branch clerk -> agent-orchestrator
- plan drafter and branch manager -> agent-planner
- Codex worker bridge -> agent-executor
- mechanical reviewer -> agent-reviewer
- integration clerk, curator draft, and curator -> agent-integrator

DeepSeek V4 Flash may do bounded mechanical evidence, read-only discovery, draft planning, branch ledger summaries, integration summaries, and bounded execution when the contract is explicit.

GPT owns final planning, architecture/decomposition decisions, parallel scheduling approval, final review, final integration, high-risk security/release decisions, and governance evolution approval.

Escalate DeepSeek output to GPT on unknown, unclear, conflict, security, auth, migration, architecture, data-source mismatch, quality gate fail, large diff, or user-facing ambiguity. DeepSeek cannot approve itself, bypass quality gate, accept human exception, merge, approve release/security gates, or install governance rules except as a draft proposal.
