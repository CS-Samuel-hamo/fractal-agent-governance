# Planner Fractal Branch Governance

Planner absorbs the former branch-manager capability.

For Level 3+ or otherwise complex work, Planner must define:

- split rationale
- child branch contracts
- owned_paths, shared_paths, forbidden_paths
- provides, consumes, dependencies
- acceptance criteria and verification plan
- stop conditions and exit condition
- max_depth and loop budget
- parent aggregation requirements
- merge queue implications

Every split must reduce uncertainty, reduce surface area, or isolate risk. Do not expand recursion without an exit condition.

Parallel execution requires explicit branch scheduling evidence: dependency graph, worktree map, path locks, resource locks, non-overlapping owned paths, stable provides/consumes, independent acceptance, independent verification, and no high-risk security/auth/payment/PII/migration work.

DeepSeek or low-cost drafting may summarize branch data, but Planner retains final decomposition, max_depth exception, parallel safety, conflict arbitration, parent aggregation, and merge-readiness decisions.
