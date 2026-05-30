---
description: Run repeatable governance eval suites without modifying business code.
argument-hint: <implicit-work-discovery | integration-surface | fractal-decomposition | routing | review-quality | learning-loop | parallel-branch | full>
mode: agent-orchestrator
---

Run a governance evaluation suite using fixtures or test repositories only. Do not read secrets and do not modify business projects.

Supported suites:
- `/eval implicit-work-discovery`
- `/eval integration-surface`
- `/eval fractal-decomposition`
- `/eval routing`
- `/eval review-quality`
- `/eval learning-loop`
- `/eval parallel-branch`
- `/eval full`

Use `scripts/run-evals.py --suite <suite>` and write reports to `.zoo-agent/evals/<eval-run-id>/eval-report.json` and `.zoo-agent/evals/<eval-run-id>/eval-report.md`.
