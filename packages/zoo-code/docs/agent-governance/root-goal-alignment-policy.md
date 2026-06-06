# Root Goal Alignment Policy

Every active implementation branch must explain how it advances the current
root goal.

## Required Links

Each implementation queue item or active branch should record:

- `root_goal_link`
- `acceptance_link`
- `obligation_link`
- `expected_artifacts`

If the branch cannot connect to the root goal, it must not become active. It
should be marked `blocked`, `follow_up`, or returned to the planner.

## Reviewer Check

Reviewers must reject delivery that optimizes a local concern while leaving the
root goal untouched. Local improvements can be useful, but they belong in the
follow-up backlog unless they close a required obligation, pass a quality gate,
or resolve a BLOCKER/MAJOR review issue.
