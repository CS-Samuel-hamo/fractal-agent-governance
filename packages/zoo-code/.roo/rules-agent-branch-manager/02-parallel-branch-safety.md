# Parallel Branch Safety

GPT branch-manager decides whether branches may run concurrently. It must check dependency graph, owned paths, shared paths, provides/consumes, parent aggregation, risk, acceptance criteria, verification plan, worktree isolation, path-lock safety, and resource-lock safety.

Approval is explicit. A parallel group is valid only when all branches have:

- non-overlapping `owned_paths`
- declared `shared_paths`
- stable `provides` / `consumes`
- low or medium risk only
- no security/auth/payment/PII/migration work
- independent acceptance criteria
- independent verification plan
- independent worktree path
- checkpoint required before executor edits
- no path-lock conflict
- no semantic `resource-locks.json` conflict
- leaf execution branch only

If a branch has an unknown dependency, shared-path conflict, resource-lock conflict, unknown Proc/data-source semantics, or missing evidence plan, mark it serial or `needs_decomposition`. DeepSeek may summarize branch data but cannot approve parallel safety.
