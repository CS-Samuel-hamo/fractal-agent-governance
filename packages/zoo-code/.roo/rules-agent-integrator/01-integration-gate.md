# Integrator Rules

Integrator may proceed only with final reviewer approval, quality gate pass or valid human exception, artifact graph consistency, and parent aggregation pass when children exist.

Human exception must record reason, scope, accepted risk, rollback plan, monitoring plan, expiry, and approver. It cannot bypass security, auth, payment, PII, secret, or destructive-operation gates.

Inspect diffs and conflicts, preserve architecture, exclude unrelated edits, run final checks or record `unknown`, and produce rollback instructions.
