# Fractal Task Governance

Definition: Recursive decomposition + local autonomy + parent aggregation + global invariants.

Branch types: root, domain, workstream, task, micro. Lifecycle: proposed, scoped, active, needs_decomposition, child_delegated, child_aggregation, review, integrating, done, blocked, abandoned.

Algorithm: classify task type, identify system boundaries, identify risk boundaries, identify dependency graph, decide split/no-split, create child contracts, define parent aggregation plan.

Must split for more than two system boundaries or risk types, more than eight files, different models/permissions, unknown/unclear scope, Proc/Processor data-source difference, research need, or independently verifiable child tasks. Do not split without verifiable artifact, owner, integration contract, or when coordination cost dominates.

Parent maintains Objective Coverage, Dependency, Ownership, Risk, and Integration matrices. DeepSeek executes bounded child tasks; GPT handles final decomposition, conflicts, and aggregation.
