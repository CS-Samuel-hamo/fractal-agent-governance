# Parallel Branch Scheduling

GPT orchestrator may ask branch-manager to schedule a parallel group only after dependency graph, owned paths, path locks, risk, worktree isolation, and merge queue policy are available. Orchestrator must generate `.zoo-agent/runs/<run-id>/branch-schedule.json`, `.zoo-agent/runs/<run-id>/path-locks.json`, and `.zoo-agent/runs/<run-id>/merge-queue.json` before parallel work starts.
