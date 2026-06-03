# Hybrid GPT/DeepSeek Routing Policy

Zoo exposes five visible roles:

- agent-orchestrator
- agent-planner
- agent-executor
- agent-reviewer
- agent-integrator

Former specialist roles are internal capabilities, not visible modes:

- project profiler and branch clerk -> agent-orchestrator
- plan drafter and branch manager -> agent-planner
- Codex worker bridge -> agent-executor
- mechanical reviewer -> agent-reviewer
- integration clerk, curator draft, and curator -> agent-integrator

DeepSeek V4 Flash may handle bounded mechanical, template-driven, read-only, directly verifiable, or draft work inside those roles. GPT owns high-risk reasoning and final decisions.

## Final Decision Owners

- agent-orchestrator: workflow routing, run state, resume/redirect, executor selection
- agent-planner: final plan, architecture, decomposition, branch scheduling, resource-lock strategy
- agent-reviewer: final review verdict, security/architecture/test adequacy when triggered
- agent-integrator: integration decision, merge queue, release readiness, governance evolution install
- agent-executor: bounded implementation and Codex Worker execution only; never final approval

## Escalation Triggers

Escalate to GPT on unknown requirement, user-facing ambiguity, conflicting patterns, security/auth/payment/PII, database migration, Proc/Processor data-source mismatch, architecture uncertainty, failing quality gate, unknown test command for non-trivial coding, large multi-module diff, diagnostics regression, path-lock conflict, worktree scheduling conflict, merge queue conflict, checkpoint unavailable for required high-risk rollback, codebase indexing unavailable for high-risk shared interface or Proc/data-source change, or human exception.

DeepSeek may draft diagnostics summaries, obligation discovery, worktree status, branch ledgers, and integration summaries. DeepSeek must not approve its own output, bypass quality gate, accept human exception, make final decomposition decisions, approve parallel scheduling, merge, approve security/release gates, or directly modify global governance rules except draft proposals.
