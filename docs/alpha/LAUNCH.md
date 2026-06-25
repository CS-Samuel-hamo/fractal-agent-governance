# Launch Plan

Version: `v1.0.0-alpha.1`

## Positioning

AI Project Operator.

Give it a project. It keeps moving it forward.

Project-level Autopilot, not task-level coding agent.

## Launch Goal

Help early users understand and test the local project operator path:

1. map the project,
2. start a session,
3. inspect Cockpit,
4. continue, stop, or undo,
5. generate release / PR drafts locally,
6. file useful feedback.

## Manual Publish Commands

These are manual commands for the maintainer. Agent Runtime does not run them automatically.
This project does not assume a `main` branch. Use the release branch for alpha publishing.

```bash
git tag -a v1.0.0-alpha.1 -m "AI Project Operator v1.0.0-alpha.1"
git push origin HEAD:refs/heads/release/v1.0.0-alpha.1
git push origin v1.0.0-alpha.1
```

If the maintainer wants the GitHub homepage to show this alpha, change the default branch manually:

GitHub Settings -> Branches -> Default branch -> `release/v1.0.0-alpha.1`

## Launch Channels

- GitHub README
- GitHub release notes
- Hacker News style post
- Reddit / LocalLLaMA / ClaudeAI / OpenAI community style post
- X / LinkedIn short post
- founder note

## Feedback Loop

Use the issue templates in `.github/ISSUE_TEMPLATE/`.

## Do Not Claim

- full autonomy
- cloud sync
- remote PR creation
- GitHub API automation
- real Claude/local actual execution as generally supported
- better coding than Codex or Claude
