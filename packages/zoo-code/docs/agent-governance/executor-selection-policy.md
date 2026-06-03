# Executor Selection Policy

Executor selection follows governance intensity.

- Level 0: Zoo fast path, optional Codex CLI or DeepSeek.
- Level 1: Codex CLI preferred; DeepSeek allowed for low-risk mechanical work.
- Level 2: GPT planner approval, then bounded Codex CLI task and review gate.
- Level 3: Zoo fractal decomposition with Codex Task Pack per executable leaf branch.
- Level 4: GPT and human gate as required; Codex may only execute explicit bounded subtasks.

`scripts/select-executor.py` writes:

`.zoo-agent/runs/<run-id>/executor-selection.json`

Required fields:

```json
{
  "run_id": "",
  "task_id": "",
  "governance_level": "",
  "recommended_executor": "codex_cli|deepseek|gpt|zoo_only|human",
  "reason": "",
  "requires_task_pack": true,
  "requires_gpt_approval": false,
  "requires_human_gate": false,
  "allowed_to_fast_path": false,
  "blocking_factors": []
}
```
