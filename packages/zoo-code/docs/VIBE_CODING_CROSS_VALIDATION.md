# Vibe Coding Cross-Validation

This document defines the reusable failure-mode checklist for AI-native,
Vibe-Coding-style execution. It applies when a user gives a natural-language
goal and expects the governance system to route, execute, verify, and integrate
the result.

## Failure Modes

| Failure mode | What can go wrong | Required cross-check | Primary evidence |
| --- | --- | --- | --- |
| Goal misunderstanding | The AI treats the request as a different task, over-expands scope, or replaces the durable project goal. | Compare the current task objective with the original user request and task context write policy. | `task-contexts/<task-id>.json`, `executor-selection.json`, final response. |
| Output semantic drift | The code is syntactically valid but does not satisfy the requested behavior. | Check tests, diff intent, acceptance criteria, and reviewer evidence against the task objective. | test output, `codex-results/<task-id>/result.json`, reviewer notes. |
| Execution not landed | The agent drafts a plan or command but does not actually run the worker or harness. | Confirm execution closure: worker result exists, or the run is explicitly governance-only. | optimistic/planned run report, `codex-run.json`, `ai-native-summary.json`. |
| Environment and dependency failure | Dependencies, PATH, env vars, native modules, or workspace paths fail and work is skipped. | Check project readiness, architecture compatibility, and environment fingerprint before claiming readiness. | `.zoo-agent/project-readiness.json`, compatibility report, result environment fingerprint. |
| Parallel or sub-agent conflict | Parallel tasks race, overwrite artifacts, or share mutable surfaces. | Compare `parallel_contract.conflict_keys`; do not schedule overlapping writers together. | `executor-selection.json.execution_graph`, Level 3 leaf task index. |
| State and progress gaps | Logs, task boards, summaries, or merge queues are missing or stale. | Refresh run summary and compare status, task-board consistency, risk register, and merge queue. | `ai-native-summary.json`, task-board consistency, merge queue, risk register. |
| Side-effect drift | Files, branches, caches, data, secrets, or runtime state change outside the intended surface. | Run scope guard, inspect diff/status, and keep excluded dirty paths outside staging and rollback. | scope guard, git diff/status, compatibility dirty-path issues, rollback anchor. |

## Required Cross-Validation Dimensions

Every review or integration decision should cover these dimensions:

- goal consistency: final output and changed files match the original user task;
- execution validity: the worker/harness actually ran, or the run is marked governance-only;
- output correctness: tests, acceptance criteria, and reviewer checks support the result;
- state completeness: run status, task board, branch/worktree, merge queue, and summaries are current;
- resource and dependency handling: paths, env vars, locks, and dependencies are captured or blocked;
- concurrency consistency: parallel tasks have non-overlapping conflict keys or are read-only;
- repeatability: commands, inputs, environment fingerprint, and artifacts are sufficient to rerun or audit.

## Closure Rule

Do not claim merge, release, deploy, provider-probe, data-update,
cache-mutation, or durable-state readiness unless:

- execution closure is true;
- evidence closure is true;
- integration closure is true;
- no cross-validation dimension above remains unknown for the claimed action.
