# Loop Budget And Convergence

Each run must maintain `.zoo-agent/runs/<run-id>/loop-state.json`. Per branch defaults: remediation max 2, review max 2, needs_decomposition max 1, max_depth 3. Each loop checks root goal coverage, unresolved unknowns, quality gate trajectory, branch risk, owned path compliance, and required obligation closure.

Mark stalled if no improvement. Mark regressing if quality, risk, ownership, or obligations worsen. Two stalled rounds must escalate. One regressing round requires GPT review. Depth beyond max_depth requires GPT branch-manager/planner approval.
