# Demo Project

This is a synthetic demo project for the Agent Runtime public alpha.

It is intentionally small and safe:

- no secrets
- no `.env`
- no network setup
- no deployment scripts
- no real API keys

## Try The Operator Flow

```bash
agent cockpit
agent start "prepare this demo project for public release"
agent status
agent release
agent pr
```

## Project Shape

- `src/sample_app.py` contains a tiny function.
- `tests/test_sample_app.py` contains a tiny test.
- `docs/overview.md` describes the project.
- `demo_artifacts/` contains sanitized sample operator artifacts.
