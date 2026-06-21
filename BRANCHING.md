# Branching

This repository has historical branch caveats from the public alpha publishing path.

## Current Facts

- Local working branch: `master`
- Release branch: `release/v1.0.0-alpha.1`
- Release tag: `v1.0.0-alpha.1`
- Previous remote default branch observed during publishing: `release/v0.9.1-alpha`
- `main` is not assumed to exist.

## Why Not Push `master`

Local `master` and remote `origin/master` were not treated as a safe fast-forward pair during publishing. A direct push to `master` could require force or history replacement, so it is not part of the alpha path.

Use the release branch instead:

```bash
git push origin HEAD:refs/heads/release/v1.0.0-alpha.1
```

Do not force push.

## Default Branch

If maintainers want the GitHub repository homepage to show the 1.0 alpha content, change the default branch manually:

GitHub Settings -> Branches -> Default branch -> `release/v1.0.0-alpha.1`

Agent Runtime does not change the GitHub default branch automatically.
