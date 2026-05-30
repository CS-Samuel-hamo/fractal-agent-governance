# LinkedIn Post

I have been working on an experimental project around AI coding agent governance:

Fractal Agent Governance Runtime

Repo: <REPO_URL>

The core observation:

Code generation is cheap; verification and integration are still expensive.

AI coding agents are increasingly good at producing code, but real engineering work includes the surrounding obligations: compatibility, tests, security, architecture boundaries, release safety, integration, and maintenance.

This project explores a governance runtime for that layer:

- Obligation Ledger to capture implicit work
- Controlled Fractal Decomposition for complex tasks
- Hybrid GPT/DeepSeek Routing for decision versus execution work
- Quality and review gates
- Git worktree runtime for parallel exploration
- Learning loop from evals and reviews

It is alpha, local-first, and not an official Zoo Code project.

I am looking for feedback from engineers building or using agentic coding systems:

- What governance artifacts should agents produce?
- How much process is useful before it becomes too heavy?
- Where should human review remain mandatory?
