# I built a Fractal Agent Governance Runtime for Zoo Code

Repo: <REPO_URL>

I ran into a recurring problem while using AI coding agents:

AI coding agents generate code quickly, but execution models often only do the literal task and miss implicit work.

For example, "add one field" is rarely only one field. It may also require DTO updates, mapper updates, schema changes, fixtures, tests, docs, compatibility checks, and rollback notes.

I built an experimental governance runtime around that idea:

- Obligation Ledger
- Controlled Fractal Decomposition
- Hybrid GPT/DeepSeek Routing
- Quality Gates
- Worktree Runtime
- Learning Loop

The current repo includes toy demos:

- Demo 1: implicit work discovery
- Demo 2: fractal decomposition
- Demo 3: worktree parallel exploration

This is alpha and not an official Zoo Code project.

Feedback I am looking for:

- Is this useful as a Zoo Code governance pack?
- Would anyone test it?
- What should be simplified?
