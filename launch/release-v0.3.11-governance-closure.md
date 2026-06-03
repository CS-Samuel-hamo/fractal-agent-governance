# v0.3.11 Governance Closure

This release turns the latest governance design updates into executable package behavior.

## Added

- `check_task_board_consistency.py` for stale task-board and redirect-plan detection.
- `update_risk_register.py` for run-level risk state updates.
- `run_quality_gate.py` for evidence-backed gate decisions before integration.
- `process_merge_queue.py` for serial merge queue processing artifacts.
- `manage_resource_locks.py` for active lock acquisition and release.
- Active lock handling inside `run_codex_parallel_workers.py`.
- AI-native run summaries that include quality-gate status and active lock counts.

## Updated

- `/agent-run`, `/progress`, and AI-native entrypoint rules.
- Codex parallel worker docs and merge policy.
- Unified operating model, execution loop, field feedback, architecture hardening, and cross-validation docs.
- Smoke coverage for lock conflicts, task-board warnings, open-risk gate blocking, authorized quality gates, and merge queue artifacts.

## Installation

Use the attached zip asset as the global Zoo Code governance kit package, or install from `packages/zoo-code/` after cloning the repository.

After installing or updating the global kit, run project setup again for each business project that needs refreshed local `.roo` entrypoints:

```powershell
python $env:USERPROFILE\.roo\agent-governance-kit\scripts\setup_zoo_agent.py `
  --project "<projects-root>\project-name" `
  --mode existing
```

Reload VS Code / Zoo Code after updating local project entrypoints.

## Verified

- `python scripts\validate-open-source-package.py`
- `python packages\zoo-code\scripts\validate-zoo-agent-kit.py`
- `python packages\zoo-code\scripts\validate_starter_pack.py`
- `python packages\zoo-code\scripts\smoke_test.py`
