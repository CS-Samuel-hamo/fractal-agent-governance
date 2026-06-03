# Goal Contract

Every non-trivial `/agent-run` coding task must bind a `goal_id` before fractal decomposition or execution. The goal contract lives at `.zoo-agent/goals/<goal-id>.json` and must include goal_id, run_id, root_goal, user_intent, business_outcome, technical_outcome, non_goals, assumptions, constraints, success_criteria, failure_criteria, abort_conditions, risk_tolerance, quality_bar, max_depth, max_loop_budget, human_gate_required, fallback_policy, project_charter_path, charter_alignment, owner, created_at, and updated_at.

Success criteria must be verifiable. Non-goals must limit scope. Failure criteria and abort conditions define when to stop. The goal must align with the project charter mission, non-goals, quality bar, data/security constraints, human gates, and fallback/abort conditions. Missing goal contract blocks coding.
