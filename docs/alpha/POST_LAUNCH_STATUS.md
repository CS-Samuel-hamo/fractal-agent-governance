# Post Launch Status

## v1.1.0-alpha.1 Session & Cockpit Improvement

Generated: 2026-06-25T22:30:00Z

### Published

- Version: `v1.1.0-alpha.1`
- Release branch: `feat/v1.1-session-cockpit`
- Tag: `v1.1.0-alpha.1`
- Release URL: https://github.com/CS-Samuel-hamo/fractal-agent-governance/releases/tag/v1.1.0-alpha.1

### What's New

- **Undo apply**: `agent undo --apply --yes` performs git checkout with auto-stash
- **Undo preview**: shows changed files, diff stat, checkpoint commit
- **Session recovery**: cockpit sync failure no longer blocks continuation
- **Cockpit timeline**: merged chronological sort, duration, file counts
- **Attention panel**: severity badges, related modules, file paths
- **Package**: pip-installable via `pip install zoo-agent-runtime`
- **Tests**: 41 fast unit tests (0.56s) added for core modules
- **CI/CD**: automated release and PyPI publishing workflows

### Engineering

- agent.py split from 3072 lines into 5 focused modules
- 336 Python files unified under ruff format + lint
- Pre-commit hooks active for automated quality
- Docs reorganized from 44 root files to subdirectories

### Known Limitations

- Git push over HTTPS may fail on some networks (SSL renegotiation);
  use `gh release create` as workaround
- No external worker (Codex/Claude) guaranteed without local setup
- undo --apply requires --yes confirmation for safety
- undo only reverts files tracked by git checkout; new files not removed

## v1.0.0-alpha.2

- Version: `v1.0.0-alpha.2`
- Release branch: `release/v1.0.0-alpha.2`
- Tag: `v1.0.0-alpha.2`
- Release branch URL: https://github.com/CS-Samuel-hamo/fractal-agent-governance/tree/release/v1.0.0-alpha.2
- Tag URL: https://github.com/CS-Samuel-hamo/fractal-agent-governance/releases/tag/v1.0.0-alpha.2

## Verification

- Remote branch exists: True
- Remote tag exists: True
- Local tree: `64a3705393a9acdf36dc3e7f486c2ff8f78590c1`
- Remote tree: `64a3705393a9acdf36dc3e7f486c2ff8f78590c1`
- Tree equality: True
- File diff empty: True
- Commit SHA differs but tree is equal: True

## Publish Method

- Git HTTPS push was reset while uploading pack data.
- The release branch and tag were completed with a GitHub Git Data API fallback after manual verification.
- Commit SHAs can differ between local and remote because the fallback reconstructed equivalent commit objects.
- Content verification is based on tree equality, empty file diff, release branch contents, and tag target.
- A GitHub Release object was not created by the toolchain.

## Branch Caveats

- There is no `main` branch assumption for publishing.
- Local `master` and remote `origin/master` are not treated as safely pushable.
- Current default branch: `release/v0.9.1-alpha`
- Recommended default branch: `release/v1.0.0-alpha.2`
- Default branch changes must be done manually in GitHub Settings -> Branches.

## What Was Not Done

- No force push.
- No merge.
- No remote PR creation.
- No automatic default branch change.
- No remote GitHub Release object creation.

## Publishing Command Hygiene

- Hardcoded main-branch push command detected: False
- Force push command detected: False
- Unsafe GitHub write command detected: False

## Next Operational Steps

- Run post-publish smoke checks.
- Collect first-user feedback through issue templates.
- Triage first launch issues before product iteration.
- Manually change the GitHub default branch if the maintainer wants the 1.0 alpha branch as the repo homepage.

## Recommendation

Proceed to post-launch feedback triage after the manual default branch decision is made.
