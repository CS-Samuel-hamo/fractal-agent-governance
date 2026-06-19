# Integration Worktree Policy

Big task integration must happen in an isolated integration worktree. Leaf results are applied according to aggregation integration order, then integration checks run.

This stage does not merge, push, deploy, or delete worktrees. GPT/human review is required before merge suggestion.

## Required Preconditions

- parent aggregation verdict is `READY_FOR_INTEGRATION_WORKTREE`
- integration order is recorded
- unresolved blockers are empty
- required success criteria have evidence
- rollback/worktree safety is understood

## Candidate Verdicts

- `INTEGRATION_CANDIDATE_READY`
- `INTEGRATION_TESTS_FAILED`
- `INTEGRATION_CONFLICTS`
- `NEEDS_PARENT_REAGGREGATION`
- `HUMAN_DECISION_REQUIRED`

Creating a candidate report is safe by default. Actually creating the worktree requires explicit `--yes`; merge and push remain out of scope.
