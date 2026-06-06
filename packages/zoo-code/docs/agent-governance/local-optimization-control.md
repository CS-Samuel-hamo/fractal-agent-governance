# Local Optimization Control

Local optimization must not trap a branch after the root-goal obligation is
satisfied.

## Allowed Local Optimization

Continue local optimization only when it directly:

- serves the root goal
- closes a required obligation
- passes a required quality gate
- resolves a BLOCKER or MAJOR review issue

## Default Handling

Otherwise record the idea in the follow-up backlog and continue the current run.
Do not block parent aggregation, merge queue eligibility, or implementation
delivery merely because something could be polished further.
