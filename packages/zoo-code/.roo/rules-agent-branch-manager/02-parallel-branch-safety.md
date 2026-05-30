# Parallel Branch Safety

GPT branch-manager decides whether branches may run concurrently. It must check dependency graph, non-overlapping owned paths, declared shared paths, stable provides/consumes, low/medium risk only, no security/auth/payment/PII/migration, independent acceptance criteria, independent verification plan, worktree isolation, and path-lock safety.
