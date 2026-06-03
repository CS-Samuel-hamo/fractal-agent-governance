# Goal Contract

Every non-trivial `/agent-run` coding task must bind to a `goal_id` before fractal decomposition or execution. The goal contract prevents local branch work from drifting away from the user-visible outcome.

Path: `.zoo-agent/goals/<goal-id>.json`

Required fields:
- `goal_id`
- `run_id`
- `project_charter_path`
- `charter_alignment`
- `root_goal`
- `user_intent`
- `business_outcome`
- `technical_outcome`
- `non_goals`
- `assumptions`
- `constraints`
- `success_criteria`
- `failure_criteria`
- `abort_conditions`
- `risk_tolerance`
- `quality_bar`
- `max_depth`
- `max_loop_budget`
- `human_gate_required`
- `fallback_policy`
- `owner`
- `created_at`
- `updated_at`

Success criteria must be verifiable. Non-goals constrain scope and prevent scope creep. Failure criteria and abort conditions define when to stop. Unknown material fields remain `unknown` and route to GPT planner instead of being invented.

Goal contracts are per-goal and must align with the durable project charter. If the requested goal conflicts with charter mission, non-goals, quality bar, data/security constraints, human gates, or fallback/abort conditions, stop for GPT planner or user decision.
