# Final Operating Model

Version: `0.3.10-project-bootstrap-codex-parallel`

Zoo is the governance control plane. It owns goal contracts, task boards, governance intensity classification, fractal decomposition, worktree scheduling, resource locks, progress, redirect, resume, review gates, merge queues, lessons, memory, evals, and metrics.

Codex CLI is a high-speed bounded execution worker. It reads a Codex Task Pack, runs `codex exec` inside an assigned worktree, performs implementation inside the allowed scope, runs scope guard and tests, and returns evidence.

DeepSeek V4 Flash is a low-cost auxiliary worker for profiling, drafting, branch clerk work, mechanical review, task-board drafting, and status, risk, or evidence summaries.

GPT-5.5 remains the final judgment layer for final planning, branch-manager decisions, final review, integration decisions, curator approval, high-risk security, architecture, release, and human-gate decisions.

The operating split is intentional: Zoo does not compete with Codex on code-writing speed; Zoo governs. Codex does bounded execution.

## Result Flow

1. Zoo classifies governance intensity before execution.
2. Zoo selects an executor and creates a Task Pack when Codex is selected.
3. Codex CLI runs with `codex exec --cd <worktree> --sandbox workspace-write`.
4. Codex CLI output is collected as `result.json` and `result.md`.
5. Zoo runs scope guard, quality gate, review gate, and merge queue policy before integration.

Codex CLI is never the final adjudicator.
