# Feedback Control Loop

Adaptive governance needs fast feedback and explicit convergence checks. Each execution loop must measure whether the work is getting closer to the goal.

## Convergence Signals

After each loop, check:

- goal coverage increased
- unknowns decreased
- risk decreased
- quality gate moved closer to pass
- integration cost stayed controllable
- rollback remained cheap
- required obligations decreased or closed
- changed files stayed within owned_paths

## Decisions

| Status | Meaning | Required Action |
| --- | --- | --- |
| improved | evidence moved toward the goal | continue within loop budget |
| stalled | no measurable improvement | one more bounded attempt may run if budget remains |
| stalled twice | repeated no-progress loop | escalate |
| regressing | risk, unknowns, gate status, integration cost, or rollback worsened | stop and choose escalate, fallback, or redesign |

## Runtime Artifact

`scripts/check-feedback-convergence.py` writes:

`.zoo-agent/runs/<run-id>/feedback-convergence.json`

The report must include previous metrics, current metrics, classification, and next allowed action.

## Anti-Local Optimization

If exit conditions are met, move upward to parent aggregation or final report. Do not continue because the branch could be cleaner, more elegant, or more complete outside its contract.
