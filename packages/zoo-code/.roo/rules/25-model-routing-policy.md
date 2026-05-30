# Hybrid GPT/DeepSeek Routing Policy

DeepSeek V4 Flash handles bounded mechanical, template-driven, read-only, or directly verifiable work. GPT-5.5 owns high-risk reasoning and final decisions.

## DeepSeek V4 Flash Roles
- agent-executor
- agent-project-profiler
- agent-plan-drafter
- agent-branch-clerk
- agent-mechanical-reviewer
- agent-integration-clerk
- agent-curator-draft

## GPT-5.5 Roles
- agent-orchestrator
- final planner
- final branch-manager decision
- final reviewer verdict
- final integrator decision
- final curator approval

## Escalation Triggers
Escalate to GPT on unknown requirement, user-facing ambiguity, conflicting patterns, security/auth/payment/PII, database migration, Proc/Processor data-source mismatch, architecture uncertainty, failing quality gate, unknown test command for non-trivial coding, large multi-module diff, diagnostics regression, path-lock conflict, worktree scheduling conflict, merge queue conflict, checkpoint unavailable for required high-risk rollback, codebase indexing unavailable for high-risk shared interface or Proc/data-source change, or human exception.

DeepSeek may draft diagnostics summaries, obligation discovery, worktree status, and integration-clerk reports. DeepSeek must not approve its own output, bypass quality gate, accept human exception, make final decomposition decisions, approve parallel scheduling, merge, approve security/release gates, or directly modify global governance rules except draft proposals.
