# Leaf Independence Policy

Parallelism is allowed only when leaf tasks are truly independent:

- no shared files
- no shared semantic resources
- no shared API contract
- no shared DTO/schema
- no shared database table
- no shared fixture
- no dependency chain
- separate worktree
- separate output files
- separate task pack

High-risk leaves cannot run parallel actual. `HEALTHY_WITH_WARNINGS` backend disables parallel actual by default.
