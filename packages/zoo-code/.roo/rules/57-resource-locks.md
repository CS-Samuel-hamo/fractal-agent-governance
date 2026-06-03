# Resource Locks

Use `resource-locks.json` to govern both file paths and semantic resources.

Semantic resources include API contracts, DTO/schema, database tables, events, queues, feature flags, Proc/data-source semantics, fixtures, release notes, config names, and unknown shared resources.

Branches with overlapping semantic resources cannot run in parallel unless the lock is read-only or GPT branch-manager explicitly approves a shared resource with parent aggregation. Unknown non-read-only resources block parallel scheduling.
