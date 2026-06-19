# Fast / Parallel / Governed Routing

## Fast

Fast path is the default for low-coupling, low-uncertainty, low-blast-radius tasks.

It skips:

- product doc generation
- full planning loop
- fractal decomposition
- implementation queue
- governed reviewer
- lesson extraction
- eval suite
- parent aggregation
- merge queue

It records timing metrics and a minimal report.

## Parallel

Parallel path is allowed only when tasks are independent.

Unknown independence is denied. Denial writes `parallel_denial_reason`.

Required:

- no shared files
- no shared semantic resources
- no shared API contract
- no shared DTO/schema
- no shared database table
- no shared fixture
- no dependency chain
- separate worktree
- separate output file
- separate task pack

## Governed

Governed path is for high risk, broad, uncertain, schema/API/database/security, or goal-alignment-blocked work. It requires review before merge readiness.
