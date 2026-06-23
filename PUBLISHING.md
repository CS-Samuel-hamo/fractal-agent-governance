# Publishing

Agent Runtime does not assume a `main` branch exists.

The public alpha branch is:

```text
release/v1.0.0-alpha.2
```

The public alpha tag is:

```text
v1.0.0-alpha.2
```

## Detect The Current Branch

```bash
git branch --show-current
git branch -vv
git remote -v
git ls-remote --heads origin
git ls-remote --tags origin v1.0.0-alpha.2
```

## Manual Alpha Publish Path

These commands are maintainer actions. Agent Runtime does not run them automatically.

```bash
git tag -a v1.0.0-alpha.2 -m "AI Project Operator v1.0.0-alpha.2"
git push origin HEAD:refs/heads/release/v1.0.0-alpha.2
git push origin v1.0.0-alpha.2
```

If GitHub should show the alpha branch as the repo homepage, change it manually:

GitHub Settings -> Branches -> Default branch -> `release/v1.0.0-alpha.2`

## Safety Rules

- Do not force push.
- Do not overwrite `origin/master`.
- Do not assume `main` exists.
- Do not create remote PRs or GitHub Releases automatically.
- Use API fallback only as a last resort after manual confirmation and content verification.

## Verification Basis

When API fallback has been used, local and remote commit SHAs may differ. Treat content as verified only when:

- the release branch exists,
- the tag exists,
- local and remote trees are equal,
- local and remote file diff is empty.
