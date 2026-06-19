# Resource Dependency Policy

Two leaf tasks are not independent if they share files, semantic resources, API contracts, DTO/schema, database tables, fixtures, or dependency chains.

Unknown dependency means not independent. Resource map confidence `low` disables automatic parallel actual execution.

Parallel execution requires separate worktrees, separate output files, and separate task packs.
