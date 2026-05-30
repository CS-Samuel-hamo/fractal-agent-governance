# Demo Script: Worktree Parallelism

## Target Audience

Engineering teams exploring agent parallelism, maintainers of coding agent runtimes, and reviewers concerned about unsafe concurrent edits.

## 2 Minute Version

1. Open `examples/worktree-parallel-exploration/branch-schedule.json`.
2. Show docs and tests running concurrently.
3. Show API waiting for domain.
4. Open `path-locks.json` and point to parent approval on shared type.
5. Open `merge-queue.json` and show serial integration.

Core line:

Parallel exploration is cheap. Parallel integration is dangerous. The runtime separates them.

## 5 Minute Version

1. Introduce the difference between exploration and integration.
2. Show isolated worktrees in `worktree-map.json`.
3. Show path ownership in `path-locks.json`.
4. Explain why shared type changes need parent approval.
5. Walk the merge queue and gates in order.
6. End by explaining how the final integration gate prevents conflicting branch results from becoming a release.

## Files To Show

- `examples/worktree-parallel-exploration/branch-schedule.json`
- `examples/worktree-parallel-exploration/worktree-map.json`
- `examples/worktree-parallel-exploration/path-locks.json`
- `examples/worktree-parallel-exploration/merge-queue.json`

## Core Innovation To Emphasize

- Worktree Runtime isolates branch exploration.
- Path locks prevent unsafe shared edits.
- Merge Queue serializes integration after parallel work.

## Call To Action

Use `evals/parallel-branch/cases/shared-path-conflict.yaml` to test whether an agent detects unsafe shared-path parallelism.
