# Codex Safe Execution Policy

Default execution policy:

- CLI runtime is the control plane.
- Codex CLI is a bounded execution backend.
- Fast path requires cached healthy backend profile, worktree isolation, scope guard, delivery outcome, and result collection.
- Parallel actual requires independent tasks and a healthy backend without warnings.
- Governed path uses GPT final decision and bounded Codex leaf execution.

Fallback policy:

- UNHEALTHY backend: dry-run or manual task pack only.
- HEALTHY_WITH_WARNINGS: fast Level 0/1 actual allowed; parallel actual disabled by default.
- Timeout/no-output/stream failure: classify as backend failure and do not mark task delivered.
- Returncode 0 with no business diff: classify as no_delivery unless no-op evidence is specific.

The runtime never defaults to danger/full-access, network enabled, auto merge, auto push, or worktree deletion.
