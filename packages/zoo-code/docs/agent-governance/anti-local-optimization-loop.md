# Anti-Local-Optimization Loop

Fractal decomposition is for reducing execution complexity, not for unlimited local refinement.

Branch exit requires acceptance criteria satisfied, quality gate pass, no BLOCKER/MAJOR review finding, parent-owned integration surface declared, and unresolved risks closed or escalated.

Forbidden: optimizing because "it could be better", executor scope expansion, reviewer repeated non-blocking style rejection, curator global rule expansion from one low-risk failure, and done child branch changes without parent follow-up branch.

Loop limits: remediation max 2, needs_decomposition max 1, depth above max_depth requires GPT final planner/branch-manager approval. Over budget enters parent escalation. If acceptance + quality gate + mechanical review + no GPT BLOCKER/MAJOR, enter parent aggregation.
