# Safety Model

Safety supports the product; it is not the main product story.

## Defaults

- One-off tasks preview by default.
- Project sessions keep checkpoints.
- Release and PR workflows are local-only.
- Blocked zones require attention.

## Never Automatic In The Public Alpha

Agent Runtime does not automatically:

- push
- merge
- create remote PRs
- create remote branches
- deploy
- delete user files
- read `.env` contents
- read API keys

## Checkpoints And Undo

Sessions record checkpoint metadata before actual execution paths. `agent undo` shows the latest available recovery point.

## Blocked Zones

Blocked zones include:

- secrets
- authentication
- payment
- production deployment
- database migration
- destructive file operations
- auto push or merge

These should pause the session and ask for attention instead of proceeding automatically.

## Human Ownership

Trust, readiness, and risk summaries are advisory. The user remains responsible for applying changes, reviewing output, publishing releases, and deploying systems.
