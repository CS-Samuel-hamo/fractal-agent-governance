# Eval Metrics

Required score fields:
- `obligation_recall`
- `obligation_precision`
- `integration_surface_recall`
- `routing_correctness`
- `escalation_correctness`
- `decomposition_validity`
- `review_blocker_detection`
- `parallel_safety_score`
- `forbidden_action_violations`

Eval results may be appended to metrics, but full eval is not run automatically at the end of every `/agent-run`.
