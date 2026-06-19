# Large Project Execution Policy

Large projects use staged execution:

1. Big task readiness gate.
2. Big task contract.
3. Semantic resource map.
4. Leaf task contracts.
5. Leaf task readiness gate.
6. Leaf dry-run by default.
7. Parent aggregation.
8. Integration worktree check.

Default big task actual execution is disabled. High-risk leaves never run as direct Codex actual tasks. No merge, push, deploy, release, destructive cleanup, or production migration is authorized by this policy.
