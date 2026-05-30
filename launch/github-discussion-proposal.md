# Proposal: Governance Packs for Zoo Code: modes + rules + skills + commands + evals

Repo: <REPO_URL>

I am sharing an experimental community project, not a request to merge this into Zoo Code core.

The proposal is that Zoo Code could support a "governance pack" distribution format for advanced agent workflows.

A governance pack could include:

- modes
- rules
- skills
- commands
- eval cases
- launcher metadata

The motivation is that agent governance often needs more than a single mode or prompt. A full workflow may need obligation tracking, decomposition rules, review gates, quality gates, model routing, and local evals.

The experimental repo demonstrates one possible pack:

- Obligation Ledger
- Controlled Fractal Decomposition
- Hybrid GPT/DeepSeek Routing
- Quality Gates
- Worktree Runtime
- Learning Loop

Questions for maintainers:

- Is Marketplace distribution suitable for this type of pack?
- Is there a recommended packaging format for modes + rules + skills + commands + evals?
- Could this kind of project be listed as a community example?
- Are there constraints around launcher metadata or install scripts that community packs should follow?

Again, this is not a request to add the project to core. I am looking for guidance on the right extension/distribution path.
