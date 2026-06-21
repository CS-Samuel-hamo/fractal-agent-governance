# Post-release Smoke Test

Run this after manually publishing the GitHub public alpha.

## Local Simulation

```bash
agent launch --smoke
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
- No `.zoo-agent/` runtime artifacts are tracked.
- No secrets, local absolute paths, raw logs, or unsupported claims are present.

## Remote Actions

The smoke test does not push, merge, call GitHub APIs, create remote PRs, or publish releases.
