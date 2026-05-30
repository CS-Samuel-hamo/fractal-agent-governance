# Branch Manager Rules

Branch-manager owns decomposition decisions, dependency management, integration order, and parent aggregation. Branch-clerk only maintains state.

Create child contracts with owned_paths, shared_paths, forbidden_paths, provides, consumes, dependencies, acceptance criteria, stop conditions, and exit condition. Maintain Objective Coverage, Dependency, Ownership, Risk, and Integration matrices. Detect sibling and path ownership conflicts.

Track remediation_loop_count, needs_decomposition_count, max_depth, last_state_change_at, and done-branch immutability. Escalate to parent when remediation exceeds 2 loops or needs_decomposition exceeds 1 loop. Do not authorize local optimization after exit conditions are satisfied; create follow-up branch if useful.
# v3.7 Branch State Requirements

Branch-manager owns decomposition decisions. Branch-clerk only maintains ledgers and matrices.

Every child branch contract must define owner, depth, owned_paths, shared_paths, forbidden_paths, provides, consumes, dependencies, acceptance criteria, verification plan, exit condition, max_depth, and loop budget.

Branch-manager must close child exit conditions before parent aggregation and must detect sibling dependency conflicts, path ownership conflicts, and missing provides/consumes contracts.

DeepSeek may draft branch summaries. GPT must decide decomposition, max_depth exception, conflict arbitration, parent aggregation, and merge readiness.
