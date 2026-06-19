# Big Task Vs Fast Path

Fast path is for low-coupling, low-risk, bounded work. It avoids planning loops, product documentation, parent aggregation, and merge queues.

Big task runtime is for complex work. It starts with readiness, then decomposes into leaf contracts, checks semantic resources, runs task readiness, aggregates parent evidence, and only then can propose an integration worktree.

File path separation alone is not enough for parallelism. Leaf tasks must also avoid shared semantic resources, API contracts, DTO/schema, database tables, fixtures, and dependency chains.
