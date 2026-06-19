# Codex Backend Capability Profile

The Codex backend profile lives at:

`.zoo-agent/backend/codex-backend-profile.json`

It summarizes:

- Codex CLI version and platform.
- Sandbox, network, approval, and trusted-directory assumptions.
- Cached health status and TTL.
- Whether fast actual, parallel actual, or governed actual workers are allowed.
- Required safeguards: worktree, scope guard, delivery gate.
- Fallbacks: dry-run, manual task pack, DeepSeek executor, GPT planning only, human intervention.

Fast path reads the profile only. Full health is reserved for first actual use, expired health, backend failure, explicit `agent codex-health`, and parallel actual execution.
