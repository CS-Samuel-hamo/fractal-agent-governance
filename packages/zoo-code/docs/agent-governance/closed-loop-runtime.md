# Closed-Loop Runtime

Every `/agent-run` has a run_id and `.zoo-agent/runs/<run-id>/run-ledger.json` plus `artifact-graph.json`. Each phase declares input artifact, output artifact, gate status, owner, model, and next allowed states. Orchestrator advances from run-ledger, not scattered context.

Run ledger schema includes run_id, current_state, transitions, and allowed_next_states. Artifact graph links project profile, branch tree, child contracts, completion evidence, quality gate, mechanical review, semantic review, parent aggregation, integration report, event, and curator proposal.
