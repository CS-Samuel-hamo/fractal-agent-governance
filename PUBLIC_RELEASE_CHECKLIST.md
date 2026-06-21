# Public Release Checklist

Target version: `v1.0.0-alpha.1`

## Required Before Manual Publish

- [x] README first viewport says AI Project Operator.
- [x] Tagline remains: Give it a project. It keeps moving it forward.
- [x] Core differentiation remains: Project-level Autopilot, not task-level coding agent.
- [x] VERSION is `1.0.0-alpha.1`.
- [x] RELEASE_NOTES.md includes `v1.0.0-alpha.1`.
- [x] GITHUB_RELEASE_DRAFT.md exists.
- [x] Public CLI help shows only public commands.
- [x] Hidden publish/alpha/dogfood commands are not in normal help.
- [x] `.zoo-agent/` runtime artifacts are ignored.
- [x] Public docs do not contain secrets, local absolute paths, raw logs, or unsupported claims.
- [x] Demo flow can run without network, API keys, push, merge, or deployment.
- [x] Fresh clone verification can run locally.

## Never Automatic In This Release

- [x] No push.
- [x] No merge.
- [x] No GitHub API call.
- [x] No remote PR creation.
- [x] No remote GitHub release creation.
- [x] No artifact upload.
- [x] No production deployment.

## Manual Publish Commands

Review the generated preflight report before running any command.

```bash
git tag -a v1.0.0-alpha.1 -m "AI Project Operator v1.0.0-alpha.1"
git push origin main
git push origin v1.0.0-alpha.1
```

These commands are suggestions for the user to run manually. Agent Runtime does not run them automatically.
