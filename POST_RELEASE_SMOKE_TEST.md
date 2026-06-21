# Post-release Smoke Test

Run this after manually publishing the GitHub public alpha.

## Local Simulation

```bash
agent launch --smoke
agent postlaunch --verify
agent postlaunch --branch-audit
agent postlaunch --report
```

## Manual Checks

- VERSION exists and says `1.0.0-alpha.1`.
- README opens and says AI Project Operator.
- QUICKSTART is clear.
- `agent --help` works.
- `agent cockpit` works.
- `agent release` works.
- `agent pr` works.
- `examples/demo_project/` exists.
- GitHub issue templates exist.
- Release branch `release/v1.0.0-alpha.1` and tag `v1.0.0-alpha.1` are documented.
- `POST_LAUNCH_STATUS.md` explains the API fallback and branch caveats.
- No `.zoo-agent/` runtime artifacts are tracked.
- No secrets, local absolute paths, raw logs, or unsupported claims are present.

## Remote Actions

The smoke test and postlaunch checks do not push, merge, create tags, change default branches, create remote PRs, or publish releases.
