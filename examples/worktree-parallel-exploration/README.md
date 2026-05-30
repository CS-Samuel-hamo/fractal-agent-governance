# Demo 4: Worktree Parallel Exploration

AI coding is well suited to low-cost parallel exploration. Parallel integration is dangerous.

This demo shows a toy schedule where:

- docs branch and test branch can run concurrently
- API branch waits for domain branch
- shared type changes need parent approval
- parallel branches enter a merge queue
- final integration is serialized

The runtime uses worktree isolation, path locks, and a merge queue to separate exploration from integration.
