# Anti-Local-Optimization Loop

Fractal decomposition is for reducing execution complexity, not for unlimited local refinement.

Every branch must have finite exit conditions: acceptance criteria satisfied, quality gate pass, no BLOCKER/MAJOR review finding, parent-owned integration surface declared, and unresolved risks closed or escalated.

Forbidden loops:
- branch continues because "it could be better".
- executor expands scope by itself.
- reviewer repeatedly rejects for non-blocking style preference.
- curator expands global rules for one low-risk failure.
- done child branch keeps changing without parent follow-up branch.

Loop budgets: remediation loop max 2, `needs_decomposition` max 1, depth beyond `max_depth` requires GPT final planner/branch-manager approval. Exceeding budget routes to parent escalation.

If acceptance criteria are satisfied, quality gate passes, mechanical review passes, and GPT review has no BLOCKER/MAJOR, enter parent aggregation.
