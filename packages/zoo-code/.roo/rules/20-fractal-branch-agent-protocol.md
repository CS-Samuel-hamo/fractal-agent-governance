# Fractal Branch Agent Protocol

Fractal governance is recursive decomposition plus local autonomy plus parent aggregation plus global invariants. It reduces execution complexity; it is not unbounded recursion.

## Branch Node Schema
Each branch declares `branch_id`, `parent_branch_id`, `depth`, `branch_type`, `owner_mode`, `owner_model`, `status`, `objective`, `scope`, `non_goals`, `context_budget`, `complexity_score`, `risk_level`, `owned_paths`, `shared_paths`, `forbidden_paths`, `inputs`, `outputs`, `provides`, `consumes`, `dependencies`, `sibling_contracts`, `acceptance_criteria`, `verification_plan`, `quality_gates`, decomposition policy, integration policy, and evidence.

## Split Algorithm
Classify task type, identify system boundaries, identify risk boundaries, identify dependency graph, decide split/no-split, create child contracts, then define parent aggregation.

Must split when more than two system boundaries or risk types exist, expected changes exceed eight files, different models/permissions are needed, unknown/unclear scope exists, Proc/Processor data-source mismatch exists, research must precede implementation, or children are independently verifiable.

Do not split when children lack verifiable artifacts, no owner exists, dependencies are circular, parent cannot define an integration contract, or split only adds coordination cost.

## Parent Aggregation
Parent maintains Objective Coverage, Dependency, Ownership, Risk, and Integration matrices. Parent aggregation must pass before integration.

## Global Invariants
Child branches cannot change parent objective, modify undeclared owned paths, or change cross-branch contracts without escalation. Shared types/utilities require search first. DeepSeek cannot decide its own decomposition or merge. GPT handles final conflicts and aggregation.
# v3.7 Recursive Runtime Requirements

Fractal governance runs above Zoo Boomerang Tasks. Boomerang delegates subtasks; fractal governance controls recursive split, ownership, depth, worktree isolation, path locks, and parent aggregation.

Each non-trivial branch node must include `branch_id`, `parent_branch_id`, `depth`, `branch_type`, `owner_mode`, `owner_model`, `status`, `objective`, `scope`, `non_goals`, `owned_paths`, `shared_paths`, `forbidden_paths`, `provides`, `consumes`, `dependencies`, `acceptance_criteria`, `verification_plan`, `quality_gates`, `exit_condition`, `max_depth`, `loop_budget`, and `evidence`.

Child task still complex: return `needs_decomposition`; do not force a local patch. GPT branch-manager decides deeper split. Default `max_depth` is 3, remediation loop budget is 2, and `needs_decomposition` budget is 1 per branch.

If acceptance criteria are satisfied, quality gate passes, required obligations are closed/deferred/escalated, mechanical review passes, and GPT has no BLOCKER/MAJOR, the branch must enter parent aggregation and stop local optimization.
