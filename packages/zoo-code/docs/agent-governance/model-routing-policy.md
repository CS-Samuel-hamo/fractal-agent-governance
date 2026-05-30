# Hybrid GPT/DeepSeek Routing Policy

DeepSeek V4 Flash roles: agent-project-profiler, agent-plan-drafter, agent-branch-clerk, agent-mechanical-reviewer, agent-integration-clerk, agent-curator-draft, agent-executor.

GPT-5.5 roles: agent-orchestrator, agent-planner final approval, agent-branch-manager final decision, agent-reviewer final verdict, agent-integrator final merge decision, agent-curator final governance approval.

Escalate DeepSeek output to GPT on unknown, unclear, conflict, security, auth, migration, architecture, data-source mismatch, quality gate fail, large diff, or user-facing ambiguity. DeepSeek cannot approve itself, bypass quality gate, accept human exception, or directly modify governance rules except draft proposal.

Cost routing: DeepSeek does mechanical evidence and bounded execution. GPT receives compressed evidence, diff summary, risk report, and decision points.
