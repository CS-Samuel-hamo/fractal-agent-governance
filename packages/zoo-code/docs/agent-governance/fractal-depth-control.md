# Fractal Depth Control

Default limits:

- `max_depth = 3`
- remediation loop per branch: 2
- `needs_decomposition` per branch: 1
- stalled loops before escalation: 2
- regressing loops before GPT review: 1

Depth beyond `max_depth` requires GPT final planner or branch-manager approval. DeepSeek may report depth pressure but cannot approve deeper recursion.

Depth is justified only when a child can produce independent evidence and reduce uncertainty, risk, integration cost, or verification complexity.

Do not split when:

- child task has no verifiable output
- child has no owner
- strong circular dependency exists
- parent cannot define merge contract
- split only adds coordination cost

When depth, loop budget, or integration cost prevents progress, stop recursion and move to escalate, fallback, or abort.
