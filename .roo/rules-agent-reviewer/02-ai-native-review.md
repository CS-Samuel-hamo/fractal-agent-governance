# AI-Native Review Rule

Review AI-native runs by evidence, not by prompt confidence.

Use:

- `ai-native-summary.json`
- `ai-native-summary.json.governance_state`
- dispatcher report
- optimistic/planned isolated run report
- codex result report
- project readiness and architecture compatibility report when present
- goal alignment report from `.zoo-agent/runs/<run-id>/goal-alignment/<task-id>.json`
- merge queue, parent aggregation, risk register, and task-board consistency
- `quality-gate.json` from `run_quality_gate.py`
- git diff and test output
- `docs/VIBE_CODING_CROSS_VALIDATION.md` when present

Classify findings by behavioral risk. If scope guard fails, request escalation rather than retrying blindly.

Cross-check goal alignment, execution validity, output correctness, state
completeness, resource/dependency handling, concurrency consistency, and
repeatability before saying the task is done.

If task-board, risk, or quality evidence is missing, ask the orchestrator to run
`check_task_board_consistency.py`, `update_risk_register.py` when risks are
known, and `run_quality_gate.py` before any integration claim.
The quality gate checks goal-alignment artifacts by default; missing or blocked
alignment must be treated as review-blocking evidence unless explicitly
accepted for legacy/governance-only runs.

Do not treat reviewer approval, passing tests, or parent aggregation as merge
readiness when the merge queue is record-only, a final gate is pending, or open
run-level risks remain uncarried.

