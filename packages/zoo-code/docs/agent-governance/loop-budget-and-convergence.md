# Loop Budget And Convergence

Each run maintains `.zoo-agent/runs/<run-id>/loop-state.json`. Every branch records remediation_count, review_count, needs_decomposition_count, curator_update_count, max_remediation_loops, max_review_loops, max_needs_decomposition, max_depth, convergence_status, stalled_count, and regressing_count.

Defaults:
- remediation loops per branch: 2
- review loops per branch: 2
- needs_decomposition loops per branch: 1
- max_depth: 3

Every loop checks:
- root goal coverage increased
- unresolved unknowns decreased
- quality gate moved closer to pass
- branch risk decreased
- changed files stayed within owned_paths
- required obligations decreased or closed

If none improved, mark `stalled`. If any worsened, mark `regressing`. Two stalled rounds must escalate. One regressing round requires GPT review. Depth beyond max_depth requires GPT branch-manager or planner approval.
