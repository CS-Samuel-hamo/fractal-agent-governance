# Governance Evaluation System

Validate, quality-gate, and smoke tests are gates. They prove a package or run can proceed. They are not a full evaluation system.

Eval measures whether the governance system itself behaves well across repeated cases. Evals are repeatable, use fixtures or test repositories by default, do not read secrets, do not modify business projects, and produce reports under `.zoo-agent/evals/<eval-run-id>/`.

Supported suites:
- implicit-work-discovery
- integration-surface
- fractal-decomposition
- routing
- review-quality
- learning-loop
- parallel-branch
- full
