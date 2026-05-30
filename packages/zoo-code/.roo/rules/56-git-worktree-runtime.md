# Git Worktree Runtime

Worktrees are required for parallel coding and optional for sequential branch isolation.

Rules:

- fractal branch does not imply concurrency
- default branch execution is dependency-ordered and sequential
- parallel coding requires `worktree-map.json`, `branch-schedule.json`, and `path-locks.json`
- branch owned_paths must not overlap unless shared_paths explicitly permits coordination
- high/critical risk and security/auth/payment/PII/migration work cannot run in parallel
- completed parallel branches enter merge queue and cannot merge directly
- integration branch is single-threaded
- GPT branch-manager/orchestrator decides parallel group
- GPT integrator processes merge queue serially
- DeepSeek cannot decide parallel safety
