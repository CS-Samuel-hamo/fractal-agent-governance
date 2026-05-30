# Decision Record Policy

`/decision` creates `docs/agent-governance/decisions/<decision-id>.md` or `.zoo-agent/decisions/<decision-id>.json`.

Required fields:
- `decision_id`
- `run_id`
- `branch_id`
- `context`
- `options_considered`
- `decision`
- `rationale`
- `tradeoffs`
- `risks`
- `rollback_condition`
- `owner`
- `review_after`

ADR is required for public API, database schema/migration, auth/security boundary, external dependency, shared type/utility, Proc/Processor data-source strategy, dependency direction, or architecture_unknown/conflicting patterns. DeepSeek may draft; GPT approves.
