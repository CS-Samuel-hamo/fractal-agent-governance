# Parallel Exploration vs Integration

AI makes parallel exploration cheaper, but integration remains the expensive and risky step.

## Allowed Parallel Exploration

Exploration branches may run in sandbox or Git worktrees when:

- branches do not write overlapping owned_paths
- shared_paths are declared
- provides/consumes contracts are stable enough for comparison
- no high/critical risk is present
- no security/auth/payment/PII/migration path is touched
- each branch has independent acceptance criteria and verification plan
- worktree isolation is used

Exploration may produce multiple candidate patches, prototypes, or analysis reports.

Root goal planning should actively produce a branch schedule. Safe branches enter parallel phases; unsafe branches are recorded as serial or `needs_decomposition` with reasons.

## Forbidden Parallel Integration

Integration branches do not run concurrently. Only one integration path may be active for a parent at a time.

Parallel branches must enter merge queue after checks. They cannot merge directly.

## Parent Comparison Criteria

Before selecting a candidate, the parent branch must compare:

- goal coverage
- risk reduction
- unknown reduction
- integration cost
- rollback ease
- future optionality
- merge queue order
- rollback checkpoint availability

The selected candidate then enters normal integration gate. Rejected candidates are archived with rationale and are not merged.

## Model Authority

DeepSeek V4 Flash may draft candidate summaries and mechanical comparisons. GPT-5.5 branch-manager or orchestrator decides whether parallel exploration is safe and which candidate proceeds to integration.
