# Hybrid Model Routing

Use only five visible roles:

- `agent-orchestrator`
- `agent-planner`
- `agent-executor`
- `agent-reviewer`
- `agent-integrator`

Internal capability mapping:

- first-run intake and project profiling -> `agent-orchestrator`
- low-risk contract drafts, final plans, branch governance, and decomposition -> `agent-planner`
- bounded implementation and Codex Worker Bridge -> `agent-executor`
- mechanical checks, diagnostics, scope guard review, and final review -> `agent-reviewer`
- merge readiness, integration, release readiness, lessons, incidents, and governance evolution -> `agent-integrator`

DeepSeek may draft or execute bounded mechanical work inside these roles. GPT owns final plan, decomposition, review, integration, security/release, and governance-change decisions.
