# Artifact Graph Schema

Artifact types: project_profile, branch_tree, child_contract, completion_evidence, quality_gate, mechanical_review, semantic_review, parent_aggregation, integration_report, event, curator_proposal.

Each artifact has id, type, path, version, run_id, created_by, and gate_status. Edges declare dependencies. Reviewer, integrator, and curator must use same-run artifacts and reject stale or missing gates.
