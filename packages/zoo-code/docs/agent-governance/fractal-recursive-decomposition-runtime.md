# Fractal Recursive Decomposition Runtime

Fractal runtime uses Zoo Boomerang delegation as the execution substrate and adds governed recursion.

## Branch Types

- root
- domain
- workstream
- task
- micro

## Required Branch Node Fields

- `branch_id`
- `parent_branch_id`
- `depth`
- `branch_type`
- `owner_mode`
- `owner_model`
- `status`
- `objective`
- `scope`
- `non_goals`
- `owned_paths`
- `shared_paths`
- `forbidden_paths`
- `provides`
- `consumes`
- `dependencies`
- `acceptance_criteria`
- `verification_plan`
- `quality_gates`
- `exit_condition`
- `max_depth`
- `loop_budget`
- `evidence`

## Runtime Algorithm

1. Classify governance intensity.
2. If Level 0/1 and bounded, record no-split rationale.
3. If Level 2 requires propagation only, use a single branch contract.
4. If Level 3/4, create root branch.
5. Branch-manager decides split/no-split from objective, risk, dependencies, owned paths, and verification boundaries.
6. Boomerang delegates child branches.
7. Child returns completion evidence, blocked, or `needs_decomposition`.
8. Parent aggregates children through objective, dependency, ownership, risk, and integration matrices.
9. Merge queue serializes integration.

## Exit Rule

When acceptance criteria are satisfied, quality gate passes, required obligations are closed/deferred/escalated, mechanical review passes, and GPT has no BLOCKER/MAJOR, the branch must move to parent aggregation. It may not continue local refinement because the work could be better.
